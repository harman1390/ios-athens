/*
 * athens (realme Narzo 30 Pro 5G / realme 7 5G, RMX2117, MT6853) boot shim:
 * LK boots this as a gzip arm64 Image at EL1, MMU off, x0 = DTB. It stops the
 * MediaTek watchdog, takes over LK's framebuffer from /chosen/atag,videolfb
 * (whatever its address), and hands the SWEETXNU payload to loader_boot().
 * None of sweet's Qualcomm probes (UFS, GIC, IMEM restart reason, PS_HOLD)
 * run here: those addresses belong to other blocks on MediaTek.
 *
 * Unlike viva.c, a moved framebuffer is a warning, not a stop: athens' LK
 * framebuffer address is a Phase-0 measurement, so the first images must
 * report it rather than refuse.
 */
#include <stdint.h>
#include "console.h"
#include "loader.h"

/* toprgu@10007000 (mt6853.dts); register layout as Linux mtk_wdt.c. */
#define TOPRGU_WDT_MODE		0x10007000UL
#define WDT_MODE_KEY		0x22000000U
#define WDT_MODE_EN		(1U << 0)

/* DRAM is preserved across a warm reset: the kernel's binary-patched
 * checkpoint stubs write a progress number here; on the next boot the shim
 * prints the last one reached. */
#define CKPT_MAGIC		0xc256bf00UL	/* tail of the boot_args page: provably writable DRAM */

#define FDT_BEGIN_NODE		1
#define FDT_END_NODE		2
#define FDT_PROP		3
#define FDT_NOP			4

#define rsr(r) ({ uint64_t _v; __asm__ volatile("mrs %0, " r : "=r"(_v)); _v; })

static inline uint32_t rd32(uintptr_t a) { return *(volatile uint32_t *)a; }
static inline void wr32(uintptr_t a, uint32_t v) { *(volatile uint32_t *)a = v; }

static const char *stage;	/* set at runtime: no absolute pointers in data */

static void __attribute__((noreturn)) halt(void)
{
	for (;;)
		__asm__ volatile("wfe");
}

void exc_handler(uint64_t slot, uint64_t *regs)
{
	uint64_t esr = rsr("esr_el2");
	/* EC 0x18: MSR/MRS/sysreg trapped from EL1. XNU writes some regs that
	 * only exist (or are trap-configured) at EL2; skip the instruction
	 * and let the kernel continue. */
	if ((esr >> 26) == 0x18) {
		uint64_t elr = rsr("elr_el2");
		con_str("SKIP", "sysreg trap");
		con_hex("at", elr);
		con_hex("esr", esr);
		__asm__ volatile("msr elr_el2, %0" :: "r"(elr + 4));
		return;
	}
	con_clear(BLUE);
	/* slot & 3: 0 sync, 1 irq, 2 fiq, 3 serror (no string table: it would need relocations) */
	con_str("PANIC", "exception");
	con_hex2("SLOT", "n=", slot, "cpu=", rsr("mpidr_el1"));
	con_str("STAGE", stage);
	con_hex("ESR", esr);
	con_hex("ELR", rsr("elr_el2"));
	con_hex("FAR", rsr("far_el2"));
	con_hex("X30", regs[29]);
	halt();
}

void secondary_main(uint64_t idx)
{
	(void)idx;
	halt();
}

static uint32_t be32p(const uint8_t *p)
{
	return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 | p[3];
}

static int streq(const char *a, const char *b)
{
	while (*a && *a == *b)
		a++, b++;
	return *a == *b;
}

/* The kernel's embedded panic/debug log lives at panic_base (dram top, 1 MiB)
 * and its plain-text kprintf/panic strings survive a warm reset. Dump the
 * printable runs from the current and the previous panic_base so a panic we
 * could not photograph can still be read on the next boot. */
static void panic_scan(void)
{
	static const uint64_t regions[] = { 0xffd60000UL, 0x1bdf00000UL };
	char line[80];
	for (unsigned r = 0; r < sizeof(regions) / sizeof(regions[0]); r++) {
		const uint8_t *base = (const uint8_t *)regions[r];
		unsigned shown = 0;
		for (uint64_t off = 0; off < 0x100000 && shown < 24; ) {
			uint64_t start = off;
			while (off < 0x100000 && base[off] >= 0x20 && base[off] < 0x7f)
				off++;
			uint64_t len = off - start;
			off++;
			if (len < 24)
				continue;
			unsigned i = 0;
			for (unsigned h = 0; h < 8; h++)
				line[i++] = "0123456789abcdef"[(regions[r] >> (28 - h * 4)) & 0xf];
			line[i++] = ':';
			for (uint64_t j = 0; j < len && i < sizeof(line) - 1 && j < 66; j++)
				line[i++] = (char)base[start + j];
			line[i] = 0;
			con_str("PRAM", line);
			shown++;
		}
	}
}

/* fb_base from LK's /chosen/atag,videolfb (raw LE struct, maybe only 4-byte aligned). */
static uint64_t videolfb_base(uintptr_t dtb)
{
	const uint8_t *fdt = (const uint8_t *)dtb;
	if (be32p(fdt) != 0xd00dfeed)
		return 0;
	const uint8_t *p = fdt + be32p(fdt + 8);
	const char *strings = (const char *)fdt + be32p(fdt + 12);
	const uint8_t *limit = fdt + be32p(fdt + 4);

	while (p < limit) {
		uint32_t tok = be32p(p);
		p += 4;
		if (tok == FDT_BEGIN_NODE) {
			while (*p)
				p++;
			p = (const uint8_t *)(((uintptr_t)p + 4) & ~3UL);
		} else if (tok == FDT_PROP) {
			uint32_t len = be32p(p);
			const uint8_t *val = p + 8;
			if (streq(strings + be32p(p + 4), "atag,videolfb") && len >= 8) {
				uint64_t v = 0;
				for (int i = 7; i >= 0; i--)
					v = v << 8 | val[i];
				return v;
			}
			p = (const uint8_t *)(((uintptr_t)val + len + 3) & ~3UL);
		} else if (tok != FDT_END_NODE && tok != FDT_NOP) {
			break;
		}
	}
	return 0;
}

void shim_main(uint64_t dtb, uint64_t sctlr_el2_entry)
{
	stage = "watchdog";
	wr32(TOPRGU_WDT_MODE, (rd32(TOPRGU_WDT_MODE) & ~WDT_MODE_EN & 0x00ffffffU) | WDT_MODE_KEY);

	stage = "loader";
	uint64_t fb = videolfb_base(dtb);
	if (fb)
		con_fb = (volatile uint32_t *)fb;
	/* Clear only the text area: kernel checkpoint bands (rows 700+) survive
	 * a warm reset, so a reset loop still shows how far the kernel got. */
	con_clear_rows(BLACK, 600);
	con_str("SHIM", "athens: xnu loader");
	con_hex2("EL", "el=", rsr("CurrentEL") >> 2, "wdt=", rd32(TOPRGU_WDT_MODE));
	con_hex("DTB", dtb);
	/* What LK handed over at EL2 (start.S already cleaned the caches and
	 * turned the EL2 MMU/D-cache off): bit 0 M, bit 2 C. */
	if ((rsr("CurrentEL") >> 2) == 2) {
		con_hex("SCTLR2", sctlr_el2_entry);
		con_hex("HCR2", rsr("hcr_el2"));
		con_hex("CNTVOFF", rsr("cntvoff_el2"));
	}
	con_hex("LK FB", fb);
	con_hex("CKPT", rd32(CKPT_MAGIC));	/* last kernel checkpoint (survives reset) */
	con_hex("SENT", rd32(CKPT_MAGIC + 4));	/* sentinel: stays 0xDEAD if kernel never wrote */
	if (fb != FB_BASE)
		con_str("WARN", "LK fb differs from FB_BASE; kernel fbcon must match");
	panic_scan();
	con_skip();

	wr32(CKPT_MAGIC, 0);	/* reset for this attempt */
	wr32(CKPT_MAGIC + 4, 0xdead);
	const char *why = loader_boot(dtb);
	con_str("LOADER", why);
	halt();
}
