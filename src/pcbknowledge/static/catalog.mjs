import { getDocument, GlobalWorkerOptions } from '/static/vendor/pdfjs/6.2.108/pdf.min.mjs';
GlobalWorkerOptions.workerSrc = '/static/vendor/pdfjs/6.2.108/pdf.worker.min.mjs';
const status = document.querySelector('#pdf-status');
const canvas = document.querySelector('#pdf-page');
let currentTask;
let currentRender;
let sequence = 0;
async function show(button) {
  const token = ++sequence;
  status.textContent = 'Loading PDF page ' + button.dataset.page + '…';
  try {
    if (currentRender) currentRender.cancel();
    if (currentTask) await currentTask.destroy();
    if (token !== sequence) return;
    currentTask = getDocument({ url: button.dataset.url, isEvalSupported: false });
    const doc = await currentTask.promise;
    const pageNumber = Number(button.dataset.page);
    if (pageNumber < 1 || pageNumber > doc.numPages) throw new Error('Page outside source');
    const page = await doc.getPage(pageNumber);
    if (token !== sequence) return;
    const viewport = page.getViewport({ scale: 1.25 });
    canvas.width = Math.ceil(viewport.width);
    canvas.height = Math.ceil(viewport.height);
    const rendering = page.render({ canvasContext: canvas.getContext('2d'), viewport });
    currentRender = rendering;
    await rendering.promise;
    if (currentRender === rendering) currentRender = null;
    if (token === sequence) status.textContent = 'PDF page ' + pageNumber + ' of ' + doc.numPages;
  } catch (error) {
    if (token === sequence) status.textContent = 'Cannot show evidence: ' + error.message;
  }
}
for (const button of document.querySelectorAll('.evidence')) button.addEventListener('click', () => show(button));
