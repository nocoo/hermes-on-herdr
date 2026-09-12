export const clamp = (n: number) => Math.max(0, Math.min(1, n));

// Quintic smoothstep: settles with zero velocity and acceleration, without bounce.
export function ease(n: number) {
	const t = clamp(n);
	return t * t * t * (t * (t * 6 - 15) + 10);
}

export function revealState(frame: number, fps: number, reduced = false) {
	if (reduced) return { mark: 1, expand: 1, caption: 1 };
	const seconds = frame / fps;
	return {
		mark: ease(seconds / 0.5),
		expand: ease((seconds - 1.25) / 1.05),
		caption: ease((seconds - 2.5) / 0.55),
	};
}

export function entrance(
	frame: number,
	fps: number,
	duration: number,
	delay = 0,
	reduced = false,
) {
	return reduced ? 1 : ease((frame / fps - delay) / duration);
}
