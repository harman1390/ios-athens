/*
 * athens panic-forensics: write a marker + the surviving DRAM panic regions to
 * the tail of the "userdata" partition before XNU starts. Independent of the
 * kernel's UFS driver - works even when the kernel dies before its own UFS
 * init or its panic-time writes fail (every panic so far left the log tail
 * untouched). Polled SCSI on the host LK left running; WRITE(10) only.
 *
 * userdata = LUN 2, GPT first LBA 2566144 (512B) = block 320768 (4K),
 * 13049848 blocks. The kernel log tail = last 1025 blocks -> partition block
 * 13048823 = device LBA 13369591. We write 400 blocks inside that tail so the
 * recovery pull (last 1025 blocks) gets it without clashing with SWEETPAN.
 */
#include <stdint.h>
#include "console.h"

#define UFS_BASE	0x11270000UL	/* ufshci@11270000, mt6853.dts */

#define REG_IS		0x20
#define REG_HCS		0x30
#define REG_HCE		0x34
#define REG_UTRLBA	0x50
#define REG_UTRLBAU	0x54
#define REG_UTRLDBR	0x58
#define REG_UTRLCLR	0x5c
#define REG_UTRLRSR	0x60

#define HCS_DP		(1u << 0)
#define HCS_UTRLRDY	(1u << 1)

#define BLOCK		4096u
#define LUN		2
#define DUMP_LBA	(13369591u + 400u)

struct utrd {
	uint32_t dw0, dw1, dw2, dw3;
	uint32_t ucdba, ucdbau, resp, prdt;
};

struct ucd {
	uint8_t cmd[512];
	uint8_t resp[512];
	struct {
		uint32_t addr_lo, addr_hi, rsvd, dbc;
	} prdt[4];
};

static struct utrd utrl[32] __attribute__((aligned(1024)));
static struct ucd ucd __attribute__((aligned(128)));

static inline uint32_t rd(uint32_t o) { return *(volatile uint32_t *)(UFS_BASE + o); }
static inline void wr(uint32_t o, uint32_t v) { *(volatile uint32_t *)(UFS_BASE + o) = v; }

static uint64_t ticks(void)
{
	uint64_t t;
	__asm__ volatile("isb; mrs %0, cntvct_el0" : "=r"(t));
	return t;
}

/* WRITE(10) of one 4K block from buf to device LBA. 0 on success. */
static uint32_t write_block(uint32_t lba, const void *buf)
{
	static uint8_t tag;
	volatile struct utrd *t = &utrl[0];
	for (unsigned i = 0; i < sizeof(*t) / 4; i++) ((volatile uint32_t *)t)[i] = 0;
	for (unsigned i = 0; i < sizeof(ucd) / 4; i++) ((volatile uint32_t *)&ucd)[i] = 0;

	ucd.cmd[0] = 0x01;		/* COMMAND UPIU */
	ucd.cmd[1] = 0x80;		/* flags: W (host -> device) */
	ucd.cmd[2] = LUN;
	ucd.cmd[3] = ++tag;
	ucd.cmd[12] = 0;
	ucd.cmd[13] = 0;
	ucd.cmd[14] = (BLOCK >> 8) & 0xff;
	ucd.cmd[15] = BLOCK & 0xff;
	/* WRITE(10): 0x2a, lba, count 1 */
	ucd.cmd[16] = 0x2a;
	ucd.cmd[18] = lba >> 24;
	ucd.cmd[19] = lba >> 16;
	ucd.cmd[20] = lba >> 8;
	ucd.cmd[21] = lba;
	ucd.cmd[23] = 0;
	ucd.cmd[24] = 1;

	uintptr_t ucd_pa = (uintptr_t)&ucd;
	t->dw0 = (1u << 28) | (1u << 25) | (1u << 24);	/* UFS storage, host->dev */
	t->dw2 = 0x0f;
	t->ucdba = (uint32_t)ucd_pa;
	t->ucdbau = (uint32_t)(ucd_pa >> 32);
	t->resp = (512u / 4) << 16 | (512u / 4);
	ucd.prdt[0].addr_lo = (uint32_t)(uintptr_t)buf;
	ucd.prdt[0].addr_hi = (uint32_t)((uintptr_t)buf >> 32);
	ucd.prdt[0].dbc = BLOCK - 1;
	t->prdt = (1024u / 4) << 16 | 1;
	__asm__ volatile("dsb sy" ::: "memory");

	wr(REG_UTRLDBR, 1);
	uint64_t start = ticks();
	while (rd(REG_UTRLDBR) & 1) {
		if (ticks() - start > 19200000) {
			wr(REG_UTRLCLR, ~1u);
			return 1;
		}
	}
	__asm__ volatile("dsb sy" ::: "memory");
	if ((utrl[0].dw2 & 0xff) || ucd.resp[0] != 0x21 || ucd.resp[7])
		return 2;
	return 0;
}

/* Dump "SHIMDUMP" marker + count, then up to blocks 4K blocks from each source. */
int ufsdump(const uint64_t *srcs, const uint32_t *blocks, unsigned n)
{
	static uint8_t hdr[BLOCK] __attribute__((aligned(4096)));
	uint32_t hcs = rd(REG_HCS), hce = rd(REG_HCE);
	if (!(hce & 1) || !(hcs & HCS_DP) || !(hcs & HCS_UTRLRDY))
		return -1;

	wr(REG_UTRLRSR, 0);
	uintptr_t list = (uintptr_t)utrl;
	wr(REG_UTRLBA, (uint32_t)list);
	wr(REG_UTRLBAU, (uint32_t)(list >> 32));
	wr(REG_UTRLRSR, 1);
	if (rd(REG_UTRLBA) != (uint32_t)list || !(rd(REG_UTRLRSR) & 1))
		return -2;

	for (unsigned i = 0; i < BLOCK; i++) hdr[i] = 0;
	__builtin_memcpy(hdr, "SHIMDUMP", 8);
	hdr[8] = 1;				/* version */
	*(volatile uint32_t *)(hdr + 12) = n;
	uint32_t lba = DUMP_LBA;
	if (write_block(lba++, hdr))
		return -3;
	uint32_t wrote = 0;
	for (unsigned r = 0; r < n; r++) {
		for (uint32_t b = 0; b < blocks[r]; b++) {
			if (write_block(lba, (const void *)(srcs[r] + (uint64_t)b * BLOCK)))
				goto out;
			lba++;
			wrote++;
		}
	}
out:
	*(volatile uint32_t *)(hdr + 16) = wrote;
	write_block(DUMP_LBA, hdr);	/* update count */
	return wrote > 0 ? 0 : -4;
}
