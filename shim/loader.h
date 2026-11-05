#pragma once
#include <stdint.h>

/* Boot the SWEETXNU payload found in the ABL ramdisk; returns only on error. */
const char *loader_boot(uintptr_t dtb);
void enter_el1(uint64_t entry_pa, uint64_t boot_args_pa);
