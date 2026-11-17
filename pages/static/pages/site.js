document.addEventListener("error", function (event) {
  const image = event.target;
  if (!(image instanceof HTMLImageElement) || !image.matches(".book-cover img, .hero-book img, .inventory-book img, .shelf-spines img")) {
    return;
  }
  const fallback = image.dataset.fallback;
  if (fallback && image.src !== new URL(fallback, document.baseURI).href) {
    image.src = fallback;
    image.classList.add("cover-placeholder");
  }
}, true);

document.addEventListener("DOMContentLoaded", function () {
  const nav = document.querySelector("#primary-navigation");
  const navToggle = document.querySelector(".nav-toggle");

  if (nav && navToggle) {
    document.body.classList.add("nav-ready");
    const closeNavigation = function () {
      nav.classList.remove("is-open");
      navToggle.setAttribute("aria-expanded", "false");
      navToggle.setAttribute("aria-label", "Ouvrir le menu");
    };

    navToggle.addEventListener("click", function () {
      const isOpen = navToggle.getAttribute("aria-expanded") !== "true";
      nav.classList.toggle("is-open", isOpen);
      navToggle.setAttribute("aria-expanded", String(isOpen));
      navToggle.setAttribute("aria-label", isOpen ? "Fermer le menu" : "Ouvrir le menu");
    });
    nav.addEventListener("click", function (event) {
      if (event.target.closest("a")) closeNavigation();
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && nav.classList.contains("is-open")) {
        closeNavigation();
        navToggle.focus();
      }
    });
  }

  document.querySelectorAll(".password-toggle").forEach(function (toggle) {
    toggle.addEventListener("click", function () {
      const input = toggle.closest(".password-field")?.querySelector("input");
      if (!input) return;
      const visible = input.type === "password";
      input.type = visible ? "text" : "password";
      toggle.textContent = visible ? "Masquer" : "Afficher";
      toggle.setAttribute("aria-pressed", String(visible));
      toggle.setAttribute("aria-label", visible ? "Masquer le mot de passe" : "Afficher le mot de passe");
    });
  });

  document.querySelectorAll(".membership-ledger form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      event.preventDefault();
      form.closest(".membership-ledger").classList.add("ledger-closing");
      window.setTimeout(function () {
        form.submit();
      }, 420);
    });
  });

  document.querySelectorAll("[data-library-entry]").forEach(function (link) {
    link.addEventListener("click", function (event) {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      event.preventDefault();
      document.body.classList.add("library-transition");
      window.setTimeout(function () {
        window.location.assign(link.href);
      }, 520);
    });
  });

  const archiveSearch = document.querySelector("#catalogue-search");
  const worldSearch = document.querySelector("#world-search");
  const resultsCount = document.querySelector("[data-results-count]");
  let searchTimer;
  let searchRequest;

  if (archiveSearch && resultsCount) {
    const searchAcrossCatalogue = async function (value) {
      const url = new URL(window.location.href);
      url.searchParams.set("q", value);
      url.searchParams.delete("page");
      searchRequest?.abort();
      searchRequest = new AbortController();

      try {
        const response = await fetch(url, {
          headers: { "X-Requested-With": "XMLHttpRequest" },
          signal: searchRequest.signal,
        });
        if (!response.ok) throw new Error(`Catalogue search failed (${response.status})`);
        const documentText = await response.text();
        const nextPage = new DOMParser().parseFromString(documentText, "text/html");
        const nextGrid = nextPage.querySelector(".catalogue-grid");
        const nextResultsCount = nextPage.querySelector("[data-results-count]");
        if (!nextGrid || !nextResultsCount) throw new Error("Catalogue search response is incomplete");

        const currentGrid = document.querySelector(".catalogue-grid");
        currentGrid.replaceWith(nextGrid);
        resultsCount.textContent = nextResultsCount.textContent;
        resultsCount.dataset.totalResults = nextResultsCount.dataset.totalResults;

        const currentPagination = document.querySelector(".catalogue-pagination");
        const nextPagination = nextPage.querySelector(".catalogue-pagination");
        if (currentPagination && nextPagination) currentPagination.replaceWith(nextPagination);
        else if (currentPagination) currentPagination.remove();
        else if (nextPagination) {
          document.querySelector(".catalogue-results").after(nextPagination);
        }

        history.replaceState(null, "", url);
      } catch (error) {
        if (error.name !== "AbortError") {
          console.error(error);
          resultsCount.textContent = "La recherche a échoué. Réessayez.";
        }
      }
    };

    const scheduleSearch = function (value) {
      if (worldSearch) worldSearch.value = value;
      archiveSearch.value = value;
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(function () {
        searchAcrossCatalogue(value);
      }, 250);
    };

    archiveSearch.addEventListener("input", function () {
      scheduleSearch(archiveSearch.value);
    });
    worldSearch?.addEventListener("input", function () {
      scheduleSearch(worldSearch.value);
    });
  }
});
