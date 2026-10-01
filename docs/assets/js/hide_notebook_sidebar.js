const WIDE_CLASS = 'celldega-wide-notebook';
const TOGGLE_CLASS = 'celldega-notebook-nav-toggle';

function initializeNotebookLayout() {
    document.querySelectorAll(`.${TOGGLE_CLASS}`).forEach((button) => button.remove());

    // nbconvert wraps rendered notebooks in .jupyter-wrapper. Detecting the
    // generated markup is more reliable than coupling this behavior to URL
    // conventions, and makes every documentation notebook wide by default.
    const isNotebookPage = Boolean(document.querySelector('.jupyter-wrapper'));
    if (!isNotebookPage) {
        document.body.classList.remove(WIDE_CLASS);
        return;
    }

    const storageKey = `celldega-wide-notebook:${window.location.pathname}`;
    const savedPreference = window.sessionStorage.getItem(storageKey);
    let wide = savedPreference !== 'false';

    const header = document.querySelector('.md-header__inner');
    if (!header) return;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = `md-header__button ${TOGGLE_CLASS}`;

    const applyLayout = () => {
        document.body.classList.toggle(WIDE_CLASS, wide);
        const action = wide ? 'Show navigation sidebar' : 'Hide navigation sidebar';
        button.textContent = wide ? '▶' : '◀';
        button.setAttribute('aria-label', action);
        button.setAttribute('aria-pressed', String(wide));
        button.title = action;
    };

    button.addEventListener('click', () => {
        wide = !wide;
        window.sessionStorage.setItem(storageKey, String(wide));
        applyLayout();
    });

    // The left edge, immediately before the logo, visually associates the
    // control with the navigation drawer it reveals. `title` above supplies
    // the native hover tooltip in addition to the accessible label.
    header.insertBefore(button, header.firstElementChild);
    applyLayout();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeNotebookLayout);
} else {
    initializeNotebookLayout();
}

// Reinitialize after Material's optional instant-navigation page swaps.
if (window.document$?.subscribe) {
    window.document$.subscribe(initializeNotebookLayout);
}
