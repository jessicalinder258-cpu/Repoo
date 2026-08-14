import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  Highlighter,
  ImageDown,
  LoaderCircle,
  MousePointer2,
  Pencil,
  Plus,
  RotateCw,
  ShieldCheck,
  Trash2,
  Type,
  Upload,
  X,
} from 'lucide-react'
import JSZip from 'jszip'
import * as pdfjsLib from 'pdfjs-dist'
import type { PDFDocumentProxy } from 'pdfjs-dist'

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

type Tool = 'select' | 'draw' | 'highlight' | 'text'
type Point = { x: number; y: number }
type Stroke = {
  kind: 'stroke'
  points: Point[]
  color: string
  width: number
  opacity: number
}
type TextMark = {
  kind: 'text'
  x: number
  y: number
  value: string
  color: string
  size: number
}
type Mark = Stroke | TextMark

const formatBytes = (bytes: number) => {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const safeName = (name: string) => name.replace(/\.pdf$/i, '').replace(/[^\w-]+/g, '-')

function App() {
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [pageNumber, setPageNumber] = useState(1)
  const [zoom, setZoom] = useState(1)
  const [tool, setTool] = useState<Tool>('select')
  const [color, setColor] = useState('#f05a3c')
  const [textValue, setTextValue] = useState('Add a note')
  const [marks, setMarks] = useState<Record<number, Mark[]>>({})
  const [rotations, setRotations] = useState<Record<number, number>>({})
  const [renderSize, setRenderSize] = useState({ width: 0, height: 0 })
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')
  const pdfCanvasRef = useRef<HTMLCanvasElement>(null)
  const overlayRef = useRef<HTMLCanvasElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const drawingRef = useRef<Stroke | null>(null)

  const drawMarks = useCallback(
    (canvas: HTMLCanvasElement, page: number, width = canvas.width, height = canvas.height) => {
      const context = canvas.getContext('2d')
      if (!context) return
      context.clearRect(0, 0, canvas.width, canvas.height)
      const scaleX = width / canvas.width
      const scaleY = height / canvas.height
      context.save()
      context.scale(1 / scaleX, 1 / scaleY)

      for (const mark of marks[page] ?? []) {
        if (mark.kind === 'text') {
          context.globalAlpha = 1
          context.fillStyle = mark.color
          context.font = `600 ${mark.size * height}px "DM Sans", sans-serif`
          context.fillText(mark.value, mark.x * width, mark.y * height)
          continue
        }
        if (mark.points.length < 2) continue
        context.beginPath()
        context.globalAlpha = mark.opacity
        context.strokeStyle = mark.color
        context.lineWidth = mark.width * width
        context.lineCap = 'round'
        context.lineJoin = 'round'
        context.moveTo(mark.points[0].x * width, mark.points[0].y * height)
        mark.points.slice(1).forEach((point) => context.lineTo(point.x * width, point.y * height))
        context.stroke()
      }
      context.restore()
      context.globalAlpha = 1
    },
    [marks],
  )

  useEffect(() => {
    if (!document || !pdfCanvasRef.current || !overlayRef.current) return
    let cancelled = false
    const render = async () => {
      setLoading(true)
      try {
        const page = await document.getPage(pageNumber)
        const viewport = page.getViewport({
          scale: zoom * Math.min(window.devicePixelRatio || 1, 2),
          rotation: rotations[pageNumber] ?? 0,
        })
        if (cancelled) return
        const canvas = pdfCanvasRef.current!
        const overlay = overlayRef.current!
        canvas.width = viewport.width
        canvas.height = viewport.height
        overlay.width = viewport.width
        overlay.height = viewport.height
        const ratio = Math.min(window.devicePixelRatio || 1, 2)
        setRenderSize({ width: viewport.width / ratio, height: viewport.height / ratio })
        await page.render({ canvas, canvasContext: canvas.getContext('2d')!, viewport }).promise
      } catch {
        setError('This page could not be rendered. Please try another PDF.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void render()
    return () => {
      cancelled = true
    }
  }, [document, pageNumber, rotations, zoom])

  useEffect(() => {
    if (overlayRef.current) drawMarks(overlayRef.current, pageNumber)
  }, [drawMarks, pageNumber, renderSize])

  const openFile = async (selected: File) => {
    if (selected.type !== 'application/pdf' && !selected.name.toLowerCase().endsWith('.pdf')) {
      setError('Please choose a PDF file.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const bytes = await selected.arrayBuffer()
      const loaded = await pdfjsLib.getDocument({ data: bytes }).promise
      setDocument(loaded)
      setFile(selected)
      setPageNumber(1)
      setMarks({})
      setRotations({})
      setZoom(1)
    } catch {
      setError('We could not open that PDF. It may be damaged or password-protected.')
    } finally {
      setLoading(false)
    }
  }

  const normalizedPoint = (event: React.PointerEvent<HTMLCanvasElement>): Point => {
    const rect = event.currentTarget.getBoundingClientRect()
    return {
      x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
    }
  }

  const handlePointerDown = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (tool === 'select') return
    const point = normalizedPoint(event)
    if (tool === 'text') {
      if (!textValue.trim()) return
      setMarks((current) => ({
        ...current,
        [pageNumber]: [
          ...(current[pageNumber] ?? []),
          { kind: 'text', ...point, value: textValue.trim(), color, size: 0.028 },
        ],
      }))
      return
    }
    event.currentTarget.setPointerCapture(event.pointerId)
    drawingRef.current = {
      kind: 'stroke',
      points: [point],
      color: tool === 'highlight' ? '#f2b705' : color,
      width: tool === 'highlight' ? 0.032 : 0.004,
      opacity: tool === 'highlight' ? 0.62 : 1,
    }
  }

  const handlePointerMove = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawingRef.current) return
    drawingRef.current.points.push(normalizedPoint(event))
    const canvas = overlayRef.current
    if (!canvas) return
    drawMarks(canvas, pageNumber)
    const context = canvas.getContext('2d')!
    const stroke = drawingRef.current
    context.beginPath()
    context.globalAlpha = stroke.opacity
    context.strokeStyle = stroke.color
    context.lineWidth = stroke.width * canvas.width
    context.lineCap = 'round'
    stroke.points.forEach((point, index) => {
      const x = point.x * canvas.width
      const y = point.y * canvas.height
      if (index === 0) context.moveTo(x, y)
      else context.lineTo(x, y)
    })
    context.stroke()
    context.globalAlpha = 1
  }

  const handlePointerUp = () => {
    if (!drawingRef.current) return
    const stroke = drawingRef.current
    drawingRef.current = null
    setMarks((current) => ({
      ...current,
      [pageNumber]: [...(current[pageNumber] ?? []), stroke],
    }))
  }

  const renderForExport = async (page: number) => {
    if (!document) throw new Error('No document')
    const pdfPage = await document.getPage(page)
    const viewport = pdfPage.getViewport({ scale: 2.4, rotation: rotations[page] ?? 0 })
    const canvas = window.document.createElement('canvas')
    canvas.width = viewport.width
    canvas.height = viewport.height
    await pdfPage.render({ canvas, canvasContext: canvas.getContext('2d')!, viewport }).promise
    const annotationCanvas = window.document.createElement('canvas')
    annotationCanvas.width = canvas.width
    annotationCanvas.height = canvas.height
    drawMarks(annotationCanvas, page)
    canvas.getContext('2d')!.drawImage(annotationCanvas, 0, 0)
    return new Promise<Blob>((resolve, reject) =>
      canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('Export failed'))), 'image/jpeg', 0.94),
    )
  }

  const downloadBlob = (blob: Blob, name: string) => {
    const url = URL.createObjectURL(blob)
    const anchor = window.document.createElement('a')
    anchor.href = url
    anchor.download = name
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const exportCurrent = async () => {
    if (!file) return
    setExporting(true)
    setError('')
    try {
      downloadBlob(await renderForExport(pageNumber), `${safeName(file.name)}-page-${pageNumber}.jpg`)
    } catch {
      setError('The JPG export failed. Please try again.')
    } finally {
      setExporting(false)
    }
  }

  const exportAll = async () => {
    if (!file || !document) return
    setExporting(true)
    setError('')
    try {
      const zip = new JSZip()
      for (let page = 1; page <= document.numPages; page += 1) {
        zip.file(`${safeName(file.name)}-page-${page}.jpg`, await renderForExport(page))
      }
      downloadBlob(await zip.generateAsync({ type: 'blob' }), `${safeName(file.name)}-jpg-pages.zip`)
    } catch {
      setError('The ZIP export failed. Please try again.')
    } finally {
      setExporting(false)
    }
  }

  const closeDocument = () => {
    document?.cleanup()
    setDocument(null)
    setFile(null)
    setMarks({})
    setError('')
  }

  if (!document) {
    return (
      <main className="landing">
        <header className="topbar landing-bar">
          <a className="brand" href="/" aria-label="Paperlight home">
            <span className="brand-mark"><FileText size={19} /></span>
            Paperlight
          </a>
          <div className="privacy-pill"><ShieldCheck size={15} /> Files stay on your device</div>
        </header>
        <section className="hero">
          <div className="eyebrow"><span /> SIMPLE PDF TOOLKIT</div>
          <h1>Turn your PDF into<br /><em>picture-perfect</em> JPGs.</h1>
          <p className="hero-copy">Add notes, draw, highlight, rotate, and export crisp images—all from your browser.</p>
          <div
            className={`drop-zone ${dragging ? 'is-dragging' : ''}`}
            onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault()
              setDragging(false)
              const selected = event.dataTransfer.files[0]
              if (selected) void openFile(selected)
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              onChange={(event) => {
                const selected = event.target.files?.[0]
                if (selected) void openFile(selected)
              }}
            />
            <div className="upload-icon">{loading ? <LoaderCircle className="spin" /> : <Upload />}</div>
            <h2>{loading ? 'Opening your PDF…' : 'Drop your PDF here'}</h2>
            <p>or choose a file from your device</p>
            <button className="primary-button" onClick={() => fileInputRef.current?.click()} disabled={loading}>
              <Plus size={18} /> Choose PDF
            </button>
            <small>PDF up to 100 MB</small>
          </div>
          {error && <div className="error-message">{error}</div>}
          <div className="features">
            <span><Pencil size={17} /> Annotate</span>
            <span><RotateCw size={17} /> Rotate pages</span>
            <span><ImageDown size={17} /> High-quality JPG</span>
          </div>
        </section>
        <footer>Private by design · No uploads · No account needed</footer>
      </main>
    )
  }

  const currentMarks = marks[pageNumber] ?? []
  return (
    <main className="editor">
      <header className="topbar editor-bar">
        <a className="brand" href="/" onClick={(event) => { event.preventDefault(); closeDocument() }}>
          <span className="brand-mark"><FileText size={19} /></span> Paperlight
        </a>
        <div className="file-name"><FileText size={16} /><span>{file?.name}</span><small>{file && formatBytes(file.size)}</small></div>
        <button className="icon-button" onClick={closeDocument} aria-label="Close PDF"><X size={19} /></button>
      </header>

      <div className="editor-body">
        <aside className="pages-panel">
          <div className="panel-heading"><span>Pages</span><small>{document.numPages}</small></div>
          <div className="page-list">
            {Array.from({ length: document.numPages }, (_, index) => index + 1).map((page) => (
              <button
                key={page}
                className={`page-card ${page === pageNumber ? 'active' : ''}`}
                onClick={() => setPageNumber(page)}
              >
                <span className="page-sheet"><FileText size={25} strokeWidth={1.4} /></span>
                <span>Page {page}</span>
                {(marks[page]?.length ?? 0) > 0 && <i />}
              </button>
            ))}
          </div>
        </aside>

        <section className="workspace">
          <div className="toolbar">
            <div className="tool-group">
              <button aria-label="Select" className={tool === 'select' ? 'selected' : ''} onClick={() => setTool('select')} title="Select"><MousePointer2 size={18} /></button>
              <button aria-label="Draw" className={tool === 'draw' ? 'selected' : ''} onClick={() => setTool('draw')} title="Draw"><Pencil size={18} /></button>
              <button aria-label="Highlight" className={tool === 'highlight' ? 'selected' : ''} onClick={() => setTool('highlight')} title="Highlight"><Highlighter size={18} /></button>
              <button aria-label="Add text" className={tool === 'text' ? 'selected' : ''} onClick={() => setTool('text')} title="Add text"><Type size={18} /></button>
            </div>
            {(tool === 'draw' || tool === 'text') && (
              <label className="color-control" title="Color">
                <input type="color" value={color} onChange={(event) => setColor(event.target.value)} />
              </label>
            )}
            {tool === 'text' && (
              <input className="text-control" value={textValue} onChange={(event) => setTextValue(event.target.value)} aria-label="Text to add" />
            )}
            <span className="toolbar-divider" />
            <button onClick={() => setRotations((current) => ({ ...current, [pageNumber]: ((current[pageNumber] ?? 0) + 90) % 360 }))}>
              <RotateCw size={18} /><span>Rotate</span>
            </button>
            <button
              disabled={!currentMarks.length}
              onClick={() => setMarks((current) => ({ ...current, [pageNumber]: currentMarks.slice(0, -1) }))}
            >
              <Trash2 size={18} /><span>Undo last</span>
            </button>
            <div className="zoom-control">
              <button onClick={() => setZoom((value) => Math.max(.5, value - .1))}>−</button>
              <span>{Math.round(zoom * 100)}%</span>
              <button onClick={() => setZoom((value) => Math.min(2, value + .1))}>+</button>
            </div>
          </div>

          <div className="canvas-scroller">
            {loading && <div className="canvas-loading"><LoaderCircle className="spin" /> Rendering page</div>}
            <div className="canvas-wrap" style={{ width: renderSize.width, height: renderSize.height }}>
              <canvas ref={pdfCanvasRef} />
              <canvas
                ref={overlayRef}
                className={`overlay tool-${tool}`}
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerCancel={handlePointerUp}
              />
            </div>
          </div>

          <div className="page-navigation">
            <button disabled={pageNumber === 1} onClick={() => setPageNumber((page) => page - 1)}><ChevronLeft size={18} /></button>
            <span>Page <b>{pageNumber}</b> of {document.numPages}</span>
            <button disabled={pageNumber === document.numPages} onClick={() => setPageNumber((page) => page + 1)}><ChevronRight size={18} /></button>
          </div>
        </section>

        <aside className="export-panel">
          <div>
            <div className="export-icon"><ImageDown /></div>
            <h2>Ready to export?</h2>
            <p>Save the current page or package every page as high-quality JPGs.</p>
          </div>
          <div className="export-options">
            <div><span>Format</span><strong>JPG</strong></div>
            <div><span>Quality</span><strong>High · 94%</strong></div>
          </div>
          {error && <div className="error-message compact">{error}</div>}
          <div className="export-actions">
            <button className="primary-button" onClick={exportCurrent} disabled={exporting}>
              {exporting ? <LoaderCircle className="spin" size={18} /> : <Download size={18} />}
              Export current page
            </button>
            <button className="secondary-button" onClick={exportAll} disabled={exporting}>
              <Download size={17} /> Export all as ZIP
            </button>
          </div>
          <div className="privacy-note"><ShieldCheck size={17} /><span><strong>100% private</strong>Your PDF never leaves this browser.</span></div>
        </aside>
      </div>
    </main>
  )
}

export default App
