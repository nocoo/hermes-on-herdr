"""Restore exact publisher-provided icons. No redraw, cropping, or color edits."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'research/product-logos.lock.json'
ASSETS = [
    ('codex.png', 'Codex', 'OpenAI', 'https://openai.gallerycdn.vsassets.io/extensions/openai/chatgpt/26.5908.31748/1789098174434/Microsoft.VisualStudio.Services.Icons.Default', 'https://marketplace.visualstudio.com/items?itemName=openai.chatgpt'),
    ('claude-code.png', 'Claude Code', 'Anthropic', 'https://anthropic.gallerycdn.vsassets.io/extensions/anthropic/claude-code/2.1.269/1789154383141/Microsoft.VisualStudio.Services.Icons.Default', 'https://marketplace.visualstudio.com/items?itemName=anthropic.claude-code'),
    ('grok.png', 'Grok', 'xAI', 'https://grok.com/images/android-chrome-512x512.png', 'https://grok.com'),
    ('pi.svg', 'Pi', 'Pi maintainers', 'https://pi.dev/logo-auto.svg', 'https://pi.dev'),
    ('hermes.jpg', 'Hermes Agent', 'Nous Research', 'https://raw.githubusercontent.com/NousResearch/hermes-agent/436ec489854b7110b4c5506b1f52c514fa4c3ace/apps/desktop/public/nous-girl.jpg', 'https://github.com/NousResearch/hermes-agent/blob/436ec489854b7110b4c5506b1f52c514fa4c3ace/apps/desktop/src/components/brand-mark.tsx'),
    ('herdr.png', 'Herdr', 'Herdr', 'https://herdr.dev/assets/logo.png', 'https://herdr.dev'),
    ('discord.svg', 'Discord', 'Discord', 'https://cdn.prod.website-files.com/6257adef93867e50d84d30e2/66e278299a53f5bf88615e90_Symbol.svg', 'https://discord.com/branding'),
    ('telegram.svg', 'Telegram', 'Telegram', 'https://telegram.org/img/website_icon.svg?4', 'https://telegram.org'),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    previous = json.loads(LOCK.read_text()) if LOCK.exists() else {'files': []}
    entries = previous['files'] if previous['files'] else [
        {'id': name.rsplit('.', 1)[0], 'product': product, 'owner': owner,
         'file': 'public/logos/' + name, 'url': url, 'sourcePage': page,
         'modified': False, 'license': 'Publisher brand asset. No general trademark license claimed; see research/product-logo-sources.md.',
         'use': 'Unmodified product identification in a local animation preview; no endorsement implied.'}
        for name, product, owner, url, page in ASSETS
    ]
    for entry in entries:
        target = ROOT / entry['file']
        if not target.exists():
            if args.check:
                raise SystemExit('Missing ' + entry['file'])
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + '.part')
            subprocess.run(['curl', '-fsSL', '--retry', '3', '--retry-all-errors',
                            '--connect-timeout', '10', '--max-time', '45',
                            entry['url'], '-o', str(temporary)], check=True)
            if entry.get('sha256') and sha(temporary) != entry['sha256']:
                raise SystemExit('Upstream changed; retaining original pin: ' + entry['file'])
            temporary.replace(target)
        digest = sha(target)
        if entry.get('sha256') and entry['sha256'] != digest:
            raise SystemExit('Modified local asset: ' + entry['file'])
        entry.update(sha256=digest, bytes=target.stat().st_size)
        entry.setdefault('retrievedAt', datetime.now(timezone.utc).isoformat())
        print(entry['file'], entry['bytes'], flush=True)
    if not args.check:
        LOCK.write_text(json.dumps({'scope': 'Exact authoritative assets. Copyright and trademark rights stay with each owner. This manifest is not a blanket commercial brand license.', 'files': entries}, indent=2) + '\n')


if __name__ == '__main__':
    main()
