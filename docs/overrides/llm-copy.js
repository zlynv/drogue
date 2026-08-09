/**
 * LLM Copy - Copy docs as Markdown for LLM consumption
 */

function htmlToMarkdown(element) {
  if (!element) return '';

  const clone = element.cloneNode(true);

  // Remove navigation elements, TOC, edit links
  clone.querySelectorAll('.headerlink, .md-nav, .md-sidebar, .md-source, .md-footer, nav, .toc, .tabbed-labels, .tabbed-content + .tabbed-content').forEach(el => el.remove());

  function convertNode(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      return node.textContent;
    }

    if (node.nodeType !== Node.ELEMENT_NODE) return '';

    const tag = node.tagName.toLowerCase();
    const children = Array.from(node.childNodes).map(convertNode).join('');

    switch (tag) {
      case 'h1': return `\n# ${children.trim()}\n\n`;
      case 'h2': return `\n## ${children.trim()}\n\n`;
      case 'h3': return `\n### ${children.trim()}\n\n`;
      case 'h4': return `\n#### ${children.trim()}\n\n`;
      case 'h5': return `\n##### ${children.trim()}\n\n`;
      case 'h6': return `\n###### ${children.trim()}\n\n`;
      case 'p': return `${children.trim()}\n\n`;
      case 'br': return '\n';
      case 'strong': case 'b': return `**${children.trim()}**`;
      case 'em': case 'i': return `*${children.trim()}*`;
      case 'code': {
        const parent = node.parentElement;
        if (parent && parent.tagName.toLowerCase() === 'pre') return children;
        return `\`${children}\``;
      }
      case 'pre': return `\n\`\`\`\n${children}\n\`\`\`\n\n`;
      case 'a': {
        const href = node.getAttribute('href');
        if (href && !href.startsWith('#')) return `[${children.trim()}](${href})`;
        return children;
      }
      case 'img': {
        const alt = node.getAttribute('alt') || '';
        const src = node.getAttribute('src') || '';
        return `![${alt}](${src})`;
      }
      case 'ul': return '\n' + children + '\n';
      case 'ol': return '\n' + children + '\n';
      case 'li': return `- ${children.trim()}\n`;
      case 'blockquote': return `> ${children.trim()}\n\n`;
      case 'hr': return '\n---\n\n';
      case 'table': return convertTable(node);
      case 'details': return convertDetails(node);
      case 'div': {
        if (node.classList.contains('admonition') || node.classList.contains('note') || node.classList.contains('warning')) {
          const title = node.querySelector('.admonition-title, .warning-title');
          const titleText = title ? title.textContent.trim() : 'Note';
          const body = children.replace(titleText, '').trim();
          return `!!! note "${titleText}"\n    ${body.split('\n').join('\n    ')}\n\n`;
        }
        return children;
      }
      default: return children;
    }
  }

  function convertTable(table) {
    const rows = [];
    table.querySelectorAll('tr').forEach(tr => {
      const cells = [];
      tr.querySelectorAll('th, td').forEach(cell => {
        cells.push(cell.textContent.trim().replace(/\|/g, '\\|'));
      });
      rows.push(cells);
    });

    if (rows.length === 0) return '';

    let md = '\n';
    md += '| ' + rows[0].join(' | ') + ' |\n';
    md += '| ' + rows[0].map(() => '---').join(' | ') + ' |\n';
    for (let i = 1; i < rows.length; i++) {
      md += '| ' + rows[i].join(' | ') + ' |\n';
    }
    return md + '\n';
  }

  function convertDetails(details) {
    const summary = details.querySelector('summary');
    const summaryText = summary ? summary.textContent.trim() : 'Details';
    const body = details.textContent.replace(summaryText, '').trim();
    return `\n??? note "${summaryText}"\n    ${body.split('\n').join('\n    ')}\n\n`;
  }

  return convertNode(clone).replace(/\n{3,}/g, '\n\n').trim();
}

function getPageUrl() {
  return window.location.href;
}

function getSiteUrl() {
  return window.location.origin;
}

async function copyPage() {
  const article = document.querySelector('article') || document.querySelector('.md-content');
  if (!article) {
    showToast('No content found', 'error');
    return;
  }

  const markdown = htmlToMarkdown(article);
  const header = `# ${document.title}\n\nSource: ${getPageUrl()}\n\n---\n\n`;

  try {
    await navigator.clipboard.writeText(header + markdown);
    showToast('Copied page as Markdown!');
  } catch (err) {
    // Fallback
    const textarea = document.createElement('textarea');
    textarea.value = header + markdown;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    showToast('Copied page as Markdown!');
  }
}

async function copyAllDocs() {
  showToast('Fetching all pages...', 'info');

  const siteUrl = getSiteUrl();
  const navItems = document.querySelectorAll('.md-nav__link');
  const urls = new Set();

  navItems.forEach(link => {
    const href = link.getAttribute('href');
    if (href && !href.startsWith('http') && !href.startsWith('#') && !href.startsWith('.')) {
      urls.add(href);
    }
  });

  let allContent = `# drogue Documentation\n\nSource: ${siteUrl}\n\n---\n\n`;
  let loaded = 0;
  const total = urls.size;

  for (const url of urls) {
    try {
      const fullUrl = url.startsWith('http') ? url : `${siteUrl}/${url}`;
      const response = await fetch(fullUrl);
      const html = await response.text();
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
      const article = doc.querySelector('article') || doc.querySelector('.md-content');

      if (article) {
        const title = doc.querySelector('h1')?.textContent || url;
        const markdown = htmlToMarkdown(article);
        allContent += `## ${title.trim()}\n\nSource: ${fullUrl}\n\n${markdown}\n\n---\n\n`;
      }
      loaded++;
      showToast(`Loading pages... ${loaded}/${total}`, 'info');
    } catch (err) {
      console.error(`Failed to load ${url}:`, err);
    }
  }

  try {
    await navigator.clipboard.writeText(allContent);
    showToast(`Copied ${loaded} pages as Markdown!`);
  } catch (err) {
    const textarea = document.createElement('textarea');
    textarea.value = allContent;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    showToast(`Copied ${loaded} pages as Markdown!`);
  }
}

function openAsPlainText() {
  const article = document.querySelector('article') || document.querySelector('.md-content');
  if (!article) {
    showToast('No content found', 'error');
    return;
  }

  const markdown = htmlToMarkdown(article);
  const header = `${document.title}\nSource: ${getPageUrl()}\n\n---\n\n`;
  const blob = new Blob([header + markdown], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank');
}

function openInViewMarkdown() {
  const article = document.querySelector('article') || document.querySelector('.md-content');
  if (!article) {
    showToast('No content found', 'error');
    return;
  }

  const markdown = htmlToMarkdown(article);
  const header = `# ${document.title}\n\nSource: ${getPageUrl()}\n\n---\n\n`;
  const blob = new Blob([header + markdown], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank');
}

function openInChatGPT() {
  const url = encodeURIComponent(getPageUrl());
  window.open(`https://chatgpt.com/?q=Read+from+${url}+so+I+can+ask+questions+about+it`, '_blank');
}

function openInClaude() {
  const url = getPageUrl();
  window.open(`https://claude.ai/new?q=Read+from+${url}+so+I+can+ask+questions+about+it`, '_blank');
}

function showToast(message, type = 'success') {
  const existing = document.querySelector('.llm-toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = `llm-toast llm-toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => toast.classList.add('llm-toast-show'), 10);
  setTimeout(() => {
    toast.classList.remove('llm-toast-show');
    setTimeout(() => toast.remove(), 300);
  }, 2000);
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  // Wait for Material to load
  setTimeout(initLLMCopy, 500);
});

// Also re-init on navigation (instant loading)
document.addEventListener('click', (e) => {
  if (e.target.closest('.md-nav__link')) {
    setTimeout(initLLMCopy, 500);
  }
});

function initLLMCopy() {
  // Remove existing bar if any
  const existing = document.querySelector('.llm-copy-bar');
  if (existing) existing.remove();

  const article = document.querySelector('article');
  if (!article) return;

  const bar = document.createElement('div');
  bar.className = 'llm-copy-bar';
  bar.innerHTML = `
    <button onclick="copyPage()" title="Copy this page as Markdown for LLMs">
      <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>
      Copy Page
    </button>
    <button onclick="copyAllDocs()" title="Copy all documentation pages">
      <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-1 9h-4v4h-2v-4H9V9h4V5h2v4h4v2z"/></svg>
      Copy All Docs
    </button>
    <button onclick="openInViewMarkdown()" title="View as Markdown in new tab">
      <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>
      Markdown
    </button>
    <button onclick="openAsPlainText()" title="View as plain text">
      <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zM6 20V4h7v5h5v11H6z"/></svg>
      Plain Text
    </button>
    <span class="llm-copy-divider"></span>
    <button onclick="openInChatGPT()" title="Open this page in ChatGPT">
      <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855l-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023l-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135l-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365l2.602-1.5 2.607 1.5v3.005l-2.607 1.5-2.602-1.5z"/></svg>
      ChatGPT
    </button>
    <button onclick="openInClaude()" title="Open this page in Claude">
      <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
      Claude
    </button>
  `;

  article.insertBefore(bar, article.firstChild);
}
