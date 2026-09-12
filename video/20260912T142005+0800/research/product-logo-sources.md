# Product logo provenance — visual revision 02

The user's review requires real product identities. Files are downloaded directly from publisher-controlled sites or versioned official Marketplace CDN URLs. `product-logos.lock.json` records each original URL, identifying page, retrieval time, byte count, and SHA-256. `scripts/fetch_logos.py --check` verifies local bytes without network access; without `--check`, it restores missing pinned files and refuses changed content.

- **Codex:** the verified OpenAI Marketplace listing is titled “Codex – OpenAI’s coding agent” (`openai.chatgpt`, version `26.5908.31748`). Its current icon is the OpenAI knot. It is described here as the publisher-assigned Codex extension icon, not a distinct CLI mark.
- **Claude Code:** the official Anthropic listing (`anthropic.claude-code`, version `2.1.269`) supplies the orange Claude starburst icon. No community Clawd redraw is used.
- **Grok:** grok.com links its 512 px PWA icon. The slashed-ring symbol is the Grok product icon, not xAI's company wordmark.
- **Hermes Agent:** upstream `436ec489854b7110b4c5506b1f52c514fa4c3ace`, `apps/desktop/src/components/brand-mark.tsx`, explicitly calls `nous-girl.jpg` the “Brand badge.” The [original component](logos/hermes-brand-mark.tsx) and [repository MIT license](logos/Hermes-LICENSE.txt) are retained. This updates the earlier research, which only verified the docs caduceus/favicon and could not establish the avatar's product role.
- **Herdr:** the real project at herdr.dev links `/assets/logo.png` and the `herdrdev/herdr` upstream. Its gray background belongs to the official icon and is retained. No synthetic gray scenery, floor, shadow, or background panel remains in the animation.
- **Pi:** pi.dev links the maintained coding-agent repository `earendil-works/pi`; the [repository MIT license](logos/Pi-LICENSE.txt) is retained separately. The official `logo-auto.svg` is unmodified. The composition and page explicitly use a light color scheme so its embedded dark-mode media query cannot turn it white on the light film.
- **Discord:** the brand page publishes an original blurple symbol suitable for light backgrounds. The initially downloaded white variant is retained in the manifest as a reference, but the live composition uses `discord-blurple.svg`.
- **Telegram:** the current official website's SVG favicon.
- **Slack:** the unmodified 400 px colored hash on Slack's own asset CDN, identified against the official media kit and brand center.

## Rights and review boundary

Product identity and source authenticity are verified. Public availability, a code license, or an official Marketplace listing do not by themselves establish a general commercial trademark or redistribution grant. OpenAI/Anthropic/xAI brand-kit routes were not consistently reachable from this host; the Slack brand center said it was under construction when checked. No blanket commercial license is invented here. These identities appear in the user-approved film and its source archive to identify the named products. Their source provenance and owner attribution are preserved; no publisher endorsement is implied.

Hermes/Pi software notices are preserved; they do not grant trademark rights. Third-party identities remain attributed to their owners and are used to identify the products in a factual, original diagram. No logo is recolored, tilted, stretched, clipped, or presented as a Hexly-owned mark. The official Hexly assets and fonts remain separately governed by the complete immutable kit's CREDITS and license files.

The existing Grok reviewer in pane `w2X:p3` performed a read-only source check. Its first response lacked the newly found official listing/desktop sources; after receiving these sources, it independently confirmed the Codex, Claude Code, Grok and Hermes files, dimensions and hashes. It also correctly cautioned against claiming that code licenses grant trademark rights. No delegated file edits or cross-repository writes occurred.
