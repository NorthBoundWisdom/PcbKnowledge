import {
  GlobalWorkerOptions,
  getDocument,
} from "./vendor/pdfjs/6.2.108/pdf.min.mjs";

GlobalWorkerOptions.workerSrc = new URL(
  "./vendor/pdfjs/6.2.108/pdf.worker.min.mjs",
  import.meta.url,
).href;

const documentCache = new Map();
const renderState = new WeakMap();
const MAX_OUTPUT_SCALE = 2;

function documentFor(url) {
  let promise = documentCache.get(url);
  if (promise) {
    return promise;
  }
  promise = fetch(url, {
    cache: "no-store",
    credentials: "same-origin",
    headers: { Accept: "application/pdf" },
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`PDF request failed with HTTP ${response.status}`);
      }
      return response.arrayBuffer();
    })
    .then((buffer) => getDocument({
      data: new Uint8Array(buffer),
      enableXfa: false,
      isEvalSupported: false,
      useWasm: false,
    }).promise);
  documentCache.set(url, promise);
  return promise;
}

function setStatus(card, message, isError = false) {
  const status = card.querySelector("[data-render-status]");
  if (!status) {
    return;
  }
  status.textContent = message;
  status.classList.toggle("evidence-render-error", isError);
}

async function renderCard(card) {
  const url = card.dataset.pdfUrl;
  const pageNumber = Number.parseInt(card.dataset.page || "", 10);
  const frame = card.querySelector("[data-page-frame]");
  const canvas = card.querySelector("[data-pdf-canvas]");
  if (!url || !Number.isInteger(pageNumber) || pageNumber < 1 || !frame || !canvas) {
    setStatus(card, "Evidence viewer configuration is invalid.", true);
    return;
  }

  const previous = renderState.get(card) || { generation: 0, width: 0 };
  const width = Math.floor(card.clientWidth);
  if (width < 160 || previous.width === width) {
    return;
  }
  const generation = previous.generation + 1;
  renderState.set(card, { generation, width });
  setStatus(card, `Rendering Source page ${pageNumber} locally...`);

  try {
    const pdf = await documentFor(url);
    if (pageNumber > pdf.numPages) {
      throw new Error(`Anchor page ${pageNumber} exceeds the ${pdf.numPages}-page PDF`);
    }
    const page = await pdf.getPage(pageNumber);
    const baseViewport = page.getViewport({ scale: 1 });
    const outputScale = Math.min(window.devicePixelRatio || 1, MAX_OUTPUT_SCALE);
    const cssWidth = Math.max(160, Math.floor(card.clientWidth));
    const renderScale = (cssWidth / baseViewport.width) * outputScale;
    const viewport = page.getViewport({ scale: renderScale });

    const current = renderState.get(card);
    if (!current || current.generation !== generation) {
      return;
    }

    canvas.width = Math.max(1, Math.floor(viewport.width));
    canvas.height = Math.max(1, Math.floor(viewport.height));
    const context = canvas.getContext("2d", { alpha: false });
    if (!context) {
      throw new Error("Canvas 2D rendering is unavailable");
    }
    await page.render({ canvasContext: context, viewport }).promise;

    const finalState = renderState.get(card);
    if (!finalState || finalState.generation !== generation) {
      return;
    }
    frame.hidden = false;
    setStatus(card, `Rendered Source page ${pageNumber} with the anchor overlay.`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    frame.hidden = true;
    setStatus(card, `PDF rendering failed: ${message}`, true);
  }
}

function schedule(card) {
  window.requestAnimationFrame(() => void renderCard(card));
}

const cards = Array.from(document.querySelectorAll("[data-pdf-review]"));
for (const card of cards) {
  schedule(card);
}

if ("ResizeObserver" in window) {
  const observer = new ResizeObserver((entries) => {
    for (const entry of entries) {
      if (entry.target instanceof HTMLElement) {
        schedule(entry.target);
      }
    }
  });
  for (const card of cards) {
    observer.observe(card);
  }
} else {
  window.addEventListener("resize", () => {
    for (const card of cards) {
      schedule(card);
    }
  });
}
