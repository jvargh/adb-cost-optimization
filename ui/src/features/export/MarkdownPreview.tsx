import { useRef } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSlug from 'rehype-slug';
import { slug } from 'github-slugger';
import type { Root } from 'hast';
import type { ExportArtifact } from '@/types';

const ARTIFACT_ORIGIN = 'https://assessment.invalid/';

export function MarkdownPreview({ content, path, artifacts, onPreview }: {
  content: string;
  path: string;
  artifacts: ExportArtifact[];
  onPreview: (artifact: ExportArtifact) => void;
}) {
  const report = useRef<HTMLElement>(null);
  const sectionIds = new Map<string, string>();
  function indexReportSections() {
    return (tree: Root) => {
      if (path !== 'reports/assessment-report.md') return;
      // Older consolidated reports use shortened contents labels; section numbers remain stable.
      for (const node of tree.children) {
        if (node.type !== 'element' || node.tagName !== 'h2') continue;
        const id = node.properties.id;
        if (typeof id !== 'string') continue;
        const number = /^report-(\d+)-/.exec(id)?.[1];
        if (number) sectionIds.set(number, id);
      }
    };
  }
  return (
    <article className="report-preview" aria-label="Rendered report" ref={report}>
      <Markdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeSlug, { prefix: 'report-' }], indexReportSections]}
        skipHtml
        components={{
          a({ href, children }) {
            if (!href) return <span>{children}</span>;
            if (href.startsWith('#')) {
              let fragment: string;
              try {
                fragment = decodeURIComponent(href.slice(1));
              } catch {
                return <span>{children} (invalid section link)</span>;
              }
              const section = /^(\d+)-/.exec(fragment)?.[1];
              const id = (section && sectionIds.get(section)) || `report-${slug(fragment)}`;
              return <a href={`#${id}`} onClick={event => {
                const target = document.getElementById(id);
                if (target && report.current?.contains(target)) {
                  event.preventDefault();
                  target.tabIndex = -1;
                  target.focus({ preventScroll: true });
                  target.scrollIntoView({ block: 'start' });
                }
              }}>{children}</a>;
            }
            if (/^https?:\/\//i.test(href)) {
              return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
            }
            let target: URL;
            try {
              target = new URL(href, new URL(path, ARTIFACT_ORIGIN));
            } catch {
              return <span>{children} (invalid artifact link)</span>;
            }
            const artifact = artifacts.find(item => new URL(item.relativePath, ARTIFACT_ORIGIN).href === target.href);
            if (artifact && artifact.kind !== 'xlsx') {
              return <button className="report-artifact-link" type="button" onClick={() => onPreview(artifact)}>{children}</button>;
            }
            return <span>{children} <span className="muted">(see Run artifacts)</span></span>;
          },
          img({ alt }) {
            return <span className="muted">[Image omitted{alt ? `: ${alt}` : ''}]</span>;
          },
          table({ children }) {
            return <div className="report-table-scroll" role="region" aria-label="Report table" tabIndex={0}><table>{children}</table></div>;
          },
        }}
      >{content}</Markdown>
    </article>
  );
}
