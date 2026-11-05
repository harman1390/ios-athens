#pragma once
#include <stdint.h>

#if defined(VIVA)
#define FB_BASE		0x7bc10000UL	/* LK atag,videolfb fb_base (measured) */
#define FB_W		1080
#define FB_H		2400
#define FB_STRIDE	(1088 * 4)	/* a8r8g8b8, MTK pads the pitch to 1088 px */
#elif defined(ATHENS)
/* MEASURE: RMX2117's LK framebuffer (atag,videolfb) is unconfirmed; the athens
 * shim runs on whatever LK reports and prints it. Same MTK 1088-px pitch pad
 * assumed for now. */
#define FB_BASE		0x7bc10000UL	/* provisional; MEASURE on the phone */
#define FB_W		1080
#define FB_H		2400
#define FB_STRIDE	(1088 * 4)	/* provisional; a8r8g8b8 */
#else
#define FB_BASE		0x9c000000UL	/* reserved-memory cont_splash_region */
#define FB_W		1080
#define FB_H		2400
#define FB_STRIDE	(FB_W * 4)	/* a8r8g8b8, matches mainline simplefb */
#endif

#define RED	0xffff0000U
#define BLUE	0xff0000a0U
#define WHITE	0xffffffffU
#define YELLOW	0xffffff00U
#define GREEN	0xff00ff00U

extern volatile uint32_t *con_fb;

void con_clear(uint32_t bg);
void con_skip(void);
void con_str(const char *label, const char *s);
void con_hex(const char *label, uint64_t v);
/* label, then "a=xxxxxxxx b=xxxxxxxx" style pairs of 32-bit values */
void con_hex2(const char *label, const char *a, uint32_t va, const char *b, uint32_t vb);
