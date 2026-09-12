import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import example from "../examples/hexly.json";
import { themes } from "../src/brand";
import { BrandLockup } from "../src/Identity";
import { VideoPreview } from "../src/Preview";
import { createProjectFilm } from "../src/project";
import { type TemplateId, templateIds } from "../src/schema";
import "./web.css";

function Demo() {
	const [template, setTemplate] = useState<TemplateId>("launch");
	const [view, setView] = useState<"video" | "deck">("video");
	const film = createProjectFilm(example, template);
	return (
		<div className="demo-shell">
			<header>
				<a href="https://hexly.ai/videos" aria-label="hexly.ai">
					<BrandLockup />
				</a>
				<span>VIDEO KIT / 1.0.0</span>
			</header>
			<main>
				<p className="demo-kicker">ONE FAMILY. FIVE EXPRESSIONS.</p>
				<h1>Ideas in motion.</h1>
				<p className="demo-intro">
					The same story, from a first frame to a final slide.
				</p>
				<nav className="demo-templates" aria-label="Templates">
					{templateIds.map((id) => (
						<button
							type="button"
							key={id}
							aria-pressed={template === id}
							onClick={() => setTemplate(id)}
						>
							{themes[id].label}
						</button>
					))}
				</nav>
				<VideoPreview
					key={template}
					config={film}
					view={view}
					onView={setView}
				/>
			</main>
			<footer>
				Hexly Video Kit · Local preview ·{" "}
				<a href="https://github.com/nocoo/hexly.ai/tree/main/packages/video-kit">
					Source & documentation ↗
				</a>
			</footer>
		</div>
	);
}
const root = document.getElementById("root");
if (!root) throw new Error("Missing root");
createRoot(root).render(
	<StrictMode>
		<Demo />
	</StrictMode>,
);
