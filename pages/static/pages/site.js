document.addEventListener("error", function (event) {
  const image = event.target;
  if (!(image instanceof HTMLImageElement) || !image.matches(".book-cover img, .hero-book img, .inventory-book img")) {
    return;
  }
  const fallback = image.dataset.fallback;
  if (fallback && image.src !== new URL(fallback, document.baseURI).href) {
    image.src = fallback;
    image.classList.add("cover-placeholder");
  }
}, true);
