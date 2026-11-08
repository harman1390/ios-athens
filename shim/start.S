/*
 * sweet boot shim entry: arm64 Linux Image header so Qualcomm ABL treats
 * us like a kernel. ABL enters at EL1, MMU/D-cache off, x0 = DTB pointer.
 */
	.section .text.head, "ax"
	.globl _head
_head:
	b	_start			/* code0 */
	.long	0			/* code1 */
	.quad	0			/* text_offset */
	.quad	_end			/* image_size (linked at 0) */
	.quad	0xa			/* flags: LE, 4K pages, place anywhere */
	.quad	0			/* res2 */
	.quad	0			/* res3 */
	.quad	0			/* res4 */
	.ascii	"ARM\x64"		/* magic */
	.long	0			/* res5 (PE offset) */

	.text
	.globl _start
_start:
	msr	daifset, #0xf
	mov	x19, x0			/* DTB pointer from ABL */
	msr	spsel, #1
	adr	x1, _stack_top
	mov	sp, x1
	mov	x20, #0			/* SCTLR_EL2 at entry (0 when entered at EL1) */
	adr	x1, vectors
	mrs	x2, CurrentEL
	cmp	x2, #(2 << 2)
	b.eq	1f
	msr	vbar_el1, x1
	b	2f
1:	msr	vbar_el2, x1
	/* realme lk enters at EL2: the shim assumes MMU and D-cache off and
	 * nothing of LK's left dirty in the caches over the XNU window. Write
	 * back + drop every line, then turn the EL2 MMU/D-cache off. */
	mrs	x20, sctlr_el2
	bl	dcache_cisw_all
	mov	x1, x20
	bic	x1, x1, #(1 << 0)	/* M */
	bic	x1, x1, #(1 << 2)	/* C */
	msr	sctlr_el2, x1
	isb
	tlbi	alle2
	dsb	sy
	bl	dcache_cisw_all
	ic	iallu
	dsb	sy
2:	isb
	/* zero .bss */
	adr	x1, _bss_start
	adr	x2, _bss_end
1:	cmp	x1, x2
	b.hs	2f
	str	xzr, [x1], #8
	b	1b
2:	mov	x0, x19
	mov	x1, x20
	bl	shim_main
3:	wfe
	b	3b

/* PSCI CPU_ON target. x0 = context id = cpu index (1..7). */
	.globl secondary_entry
secondary_entry:
	msr	daifset, #0xf
	msr	spsel, #1
	adr	x1, _sec_stacks
	add	x1, x1, x0, lsl #12
	add	x1, x1, #0x1000
	mov	sp, x1
	adr	x1, vectors
	msr	vbar_el1, x1
	isb
	bl	secondary_main
4:	wfe
	b	4b

/*
 * Exception vectors. Each slot stashes x29/x30, loads its slot number
 * and jumps to the common path, which saves x0-x28 and calls
 * exc_handler(slot, regs). IRQs return; everything else ends in the
 * on-screen panic.
 */
.macro vent slot
	.balign	0x80
	stp	x29, x30, [sp, #-16]!
	mov	x29, #\slot
	b	exc_common
.endm

	.balign	0x800
	.globl vectors
vectors:
	vent 0
	vent 1
	vent 2
	vent 3
	vent 4
	vent 5
	vent 6
	vent 7
	vent 8
	vent 9
	vent 10
	vent 11
	vent 12
	vent 13
	vent 14
	vent 15

exc_common:
	sub	sp, sp, #(30 * 8)
	stp	x0, x1, [sp, #0]
	stp	x2, x3, [sp, #16]
	stp	x4, x5, [sp, #32]
	stp	x6, x7, [sp, #48]
	stp	x8, x9, [sp, #64]
	stp	x10, x11, [sp, #80]
	stp	x12, x13, [sp, #96]
	stp	x14, x15, [sp, #112]
	stp	x16, x17, [sp, #128]
	stp	x18, x19, [sp, #144]
	stp	x20, x21, [sp, #160]
	stp	x22, x23, [sp, #176]
	stp	x24, x25, [sp, #192]
	stp	x26, x27, [sp, #208]
	str	x28, [sp, #224]
	mov	x0, x29
	mov	x1, sp
	bl	exc_handler
	ldp	x0, x1, [sp, #0]
	ldp	x2, x3, [sp, #16]
	ldp	x4, x5, [sp, #32]
	ldp	x6, x7, [sp, #48]
	ldp	x8, x9, [sp, #64]
	ldp	x10, x11, [sp, #80]
	ldp	x12, x13, [sp, #96]
	ldp	x14, x15, [sp, #112]
	ldp	x16, x17, [sp, #128]
	ldp	x18, x19, [sp, #144]
	ldp	x20, x21, [sp, #160]
	ldp	x22, x23, [sp, #176]
	ldp	x24, x25, [sp, #192]
	ldp	x26, x27, [sp, #208]
	ldr	x28, [sp, #224]
	add	sp, sp, #(30 * 8)
	ldp	x29, x30, [sp], #16
	eret

/*
 * enter_el1(entry_pa, boot_args_pa): iBoot-style handoff. XNU expects to
 * start at EL1 with the MMU off; realme lk enters the shim at EL2. Drop
 * to EL1h with a clean hypervisor state, then eret into the kernel entry.
 */
	.globl enter_el1
enter_el1:
	mov	x12, x0			/* kernel entry (dcache_cisw_all uses x0-x11) */
	mov	x13, x1			/* boot_args -> x0 */
	mov	x14, x30
	bl	dcache_cisw_all
	ic	iallu
	dsb	sy
	mov	x30, x14
	/* Same EL2 state the secondaries get (xnu 0065 sweet_secondary_entry):
	 * CPU0 must not differ from them in counter offset or timer traps. */
	msr	hstr_el2, xzr		/* no hypervisor sysreg traps */
	msr	cptr_el2, xzr		/* no FP/SIMD traps */
	msr	mdcr_el2, xzr		/* no debug/PMU traps */
	msr	vttbr_el2, xzr
	mov	x1, #3			/* EL1PCTEN | EL1PCEN: physical counter/timer untrapped */
	msr	cnthctl_el2, x1
	msr	cntvoff_el2, xzr	/* virtual counter == physical on every CPU */
	mrs	x1, ICC_SRE_EL2
	orr	x1, x1, #1		/* SRE */
	orr	x1, x1, #8		/* Enable: EL1 may use the GIC sysregs */
	msr	ICC_SRE_EL2, x1
	isb
	ldr	x1, =0x30d00800		/* SCTLR_EL1 RES1 bits, M/C/I off, LE */
	msr	sctlr_el1, x1
	mov	x1, #(1 << 31)		/* HCR_EL2.RW: EL1 is AArch64 */
	msr	hcr_el2, x1
	mov	x1, #0x3c5		/* SPSR: EL1h, DAIF masked */
	msr	spsr_el2, x1
	msr	elr_el2, x12
	mov	x1, sp			/* share the shim stack */
	msr	sp_el1, x1
	mov	x0, x13
	isb
	eret

/* Clean + invalidate all data/unified caches to the PoC by set/way
 * (Linux __flush_dcache_all). Leaf, clobbers x0-x11. */
	.globl dcache_cisw_all
dcache_cisw_all:
	dmb	sy
	mrs	x0, clidr_el1
	and	x3, x0, #0x7000000
	lsr	x3, x3, #23		/* LoC * 2 */
	cbz	x3, 5f
	mov	x10, #0
1:	add	x2, x10, x10, lsr #1	/* level * 3 */
	lsr	x1, x0, x2
	and	x1, x1, #7		/* cache type at this level */
	cmp	x1, #2
	b.lt	4f			/* no data cache */
	msr	csselr_el1, x10
	isb
	mrs	x1, ccsidr_el1
	and	x2, x1, #7
	add	x2, x2, #4		/* log2(line bytes) */
	mov	x4, #0x3ff
	and	x4, x4, x1, lsr #3	/* max way */
	clz	w5, w4
	mov	x7, #0x7fff
	and	x7, x7, x1, lsr #13	/* max set */
2:	mov	x9, x4
3:	lsl	x6, x9, x5
	orr	x11, x10, x6
	lsl	x6, x7, x2
	orr	x11, x11, x6
	dc	cisw, x11
	subs	x9, x9, #1
	b.ge	3b
	subs	x7, x7, #1
	b.ge	2b
4:	add	x10, x10, #2
	cmp	x3, x10
	b.gt	1b
5:	mov	x10, #0
	msr	csselr_el1, x10
	dsb	sy
	isb
	ret
