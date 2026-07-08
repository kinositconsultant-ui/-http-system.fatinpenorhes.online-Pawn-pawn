/**
 * AppFooter — global branded footer strip shown on every admin page.
 * Rendered by AdminLayout so it never has to be added per-page.
 */
export default function AppFooter() {
  const year = new Date().getFullYear();
  return (
    <footer
      className="mt-8 pt-5 pb-2 border-t border-stone-200 flex items-center justify-between flex-wrap gap-3 text-xs text-stone-500 print:hidden"
      data-testid="app-footer"
    >
      <div className="flex items-center gap-2 flex-wrap">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#1B2D5C]"></span>
        <span className="text-[10px] uppercase tracking-[0.22em] text-stone-500 font-semibold">
          System Management &amp; Finance
        </span>
        <span className="text-stone-300">·</span>
        <span className="font-display text-stone-700">Fatin Penhores</span>
      </div>
      <div className="flex items-center gap-3 flex-wrap">
        <a
          href="https://kinos.com.tl"
          target="_blank"
          rel="noreferrer"
          className="text-[10px] text-stone-400 tracking-wider hover:text-[#1B2D5C] transition-colors"
          data-testid="footer-powered-by"
        >
          Powered by <span className="font-semibold text-stone-500">Kinos</span>
        </a>
        <span className="text-stone-300">·</span>
        <span className="text-[10px] text-stone-400 tracking-wider">
          © {year} Fatin Penhores Unipessoal, Lda
        </span>
      </div>
    </footer>
  );
}
