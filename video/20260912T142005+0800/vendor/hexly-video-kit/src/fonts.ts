import { useEffect, useState } from "react";
import { staticFile, useDelayRender } from "remotion";
import { kitVersion } from "./brand";

let fonts: Promise<void> | undefined;
export function loadHexlyFonts() {
	fonts ??= Promise.all(
		[
			["Space Grotesk Variable", "space-grotesk.woff2"],
			["Geist Mono Variable", "geist-mono.woff2"],
			["Journey CJK", "journey-cjk.woff2"],
		].map(async ([family, file]) => {
			const face = new FontFace(
				family ?? "",
				`url(${staticFile(`video-kit/${kitVersion}/hexly/${file}`)})`,
				{ weight: "100 900" },
			);
			document.fonts.add(await face.load());
		}),
	)
		.then(() => undefined)
		.catch((error: unknown) => {
			fonts = undefined;
			throw error;
		});
	return fonts;
}

export function useHexlyFonts() {
	const { delayRender, continueRender, cancelRender } = useDelayRender();
	const [ready, setReady] = useState(false);
	useEffect(() => {
		const handle = delayRender("Load the licensed Hexly fonts");
		let active = true;
		loadHexlyFonts()
			.then(() => {
				if (active) setReady(true);
				continueRender(handle);
			})
			.catch((error: unknown) => {
				if (active) cancelRender(error);
			});
		return () => {
			active = false;
			continueRender(handle);
		};
	}, [delayRender, continueRender, cancelRender]);
	return ready;
}
