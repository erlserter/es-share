import { useEffect, useRef, useState } from "react"
import { flushSync } from "react-dom"
import {
  AlertTriangle,
  ArrowLeftRight,
  Check,
  Copy,
  Keyboard,
  Laptop,
  Monitor,
  Moon,
  MousePointerClick,
  Play,
  ShieldCheck,
  Square,
  Sun,
  Terminal,
  Upload,
  Wifi,
} from "lucide-react"

import { DeskCanvas, type EdgeOption } from "@/components/DeskCanvas"
import {
  Alert,
  AlertAction,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Kbd, KbdGroup } from "@/components/ui/kbd"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

interface KvmStatus {
  running: boolean
  mode: "server" | "client" | null
  remote_active: boolean
  client_connected: boolean
  local_ips: string[]
  accessibility_trusted: boolean
  platform: string
  screen_size: [number, number]
  logs: string[]
}

const EDGE_LABELS: Record<EdgeOption, string> = {
  right: "Sağ Kenar (Windows sağda)",
  left: "Sol Kenar (Windows solda)",
  none: "Kapalı (Sadece Kısayol)",
}

const INITIAL_STATUS: KvmStatus = {
  running: false,
  mode: null,
  remote_active: false,
  client_connected: false,
  local_ips: ["..."],
  accessibility_trusted: true,
  platform: "darwin",
  screen_size: [1800, 1169],
  logs: ["Arayüz hazır. Mac ana bilgisayar olarak seçili."],
}

function getSystemDark(): boolean {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? true
}

function readStoredScheme(): "light" | "dark" | null {
  try {
    const val = localStorage.getItem("color-scheme")
    return val === "light" || val === "dark" ? val : null
  } catch {
    return null
  }
}

function syncColorSchemeDOM(): boolean {
  const stored = readStoredScheme()
  const content = stored ?? "light dark"
  const meta = document.querySelector<HTMLMetaElement>('meta[name="color-scheme"]')
  if (meta) meta.content = content
  const renderedDark = stored ? stored === "dark" : getSystemDark()
  document.documentElement.classList.toggle("dark", renderedDark)
  return renderedDark
}

export function App() {
  const [status, setStatus] = useState<KvmStatus>(INITIAL_STATUS)
  const [tab, setTab] = useState<"server" | "client">("server")
  const [edge, setEdge] = useState<EdgeOption>("right")
  const [srvPort, setSrvPort] = useState("24800")
  const [cliHost, setCliHost] = useState("")
  const [cliPort, setCliPort] = useState("24800")
  const [mapCmdCtrl, setMapCmdCtrl] = useState(true)
  const [copied, setCopied] = useState(false)
  const [sendingFile, setSendingFile] = useState<string | null>(null)
  const [dragOverMac, setDragOverMac] = useState(false)
  const [clientError, setClientError] = useState<string | null>(null)
  const [isDark, setIsDark] = useState<boolean>(() => syncColorSchemeDOM())
  const logEndRef = useRef<HTMLDivElement | null>(null)
  const clientFileInputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)")
    const onSchemeEvent = () => setIsDark(syncColorSchemeDOM())
    mq?.addEventListener("change", onSchemeEvent)
    window.addEventListener("storage", onSchemeEvent)
    return () => {
      mq?.removeEventListener("change", onSchemeEvent)
      window.removeEventListener("storage", onSchemeEvent)
    }
  }, [])

  const toggleTheme = () => {
    const sysDark = getSystemDark()
    const targetDark = !isDark
    const target = targetDark ? "dark" : "light"
    try {
      if (targetDark === sysDark) {
        localStorage.removeItem("color-scheme")
      } else {
        localStorage.setItem("color-scheme", target)
      }
    } catch {
      // storage disabled; still update DOM
    }
    const meta = document.querySelector<HTMLMetaElement>('meta[name="color-scheme"]')
    if (meta) meta.content = targetDark === sysDark ? "light dark" : target
    document.documentElement.classList.toggle("dark", targetDark)
    setIsDark(targetDark)
  }

  async function api<T = KvmStatus>(
    path: string,
    body: Record<string, unknown> | null = null
  ): Promise<T> {
    const res = await fetch(
      path,
      body
        ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
        : { method: "GET" }
    )
    return (await res.json()) as T
  }

  const refreshStatus = async () => {
    try {
      const data = await api<KvmStatus>("/api/status")
      setStatus(data)
    } catch {
      // ignore transient polling errors
    }
  }

  useEffect(() => {
    void refreshStatus()
    const timer = window.setInterval(() => {
      void refreshStatus()
    }, 800)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [status.logs.length])

  const handleEdgeChange = async (nextEdge: EdgeOption) => {
    const applyUpdate = () => setEdge(nextEdge)
    const doc = document as Document & {
      startViewTransition?: (cb: () => void) => unknown
    }
    if (doc.startViewTransition) {
      doc.startViewTransition(() => {
        flushSync(applyUpdate)
      })
    } else {
      applyUpdate()
    }

    if (status.running && status.mode === "server") {
      try {
        const next = await api("/api/edge", { edge: nextEdge })
        setStatus(next)
      } catch {
        // ignore transient error
      }
    }
  }

  const handleSwapEdge = () => {
    const nextEdge: EdgeOption = edge === "right" ? "left" : "right"
    void handleEdgeChange(nextEdge)
  }

  const handleCopyIp = async () => {
    const primaryIp = (status.local_ips[0] ?? "").trim()
    if (!primaryIp || primaryIp === "...") return
    try {
      await navigator.clipboard.writeText(primaryIp)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      // clipboard fallback
    }
  }

  const handleStartServer = async () => {
    setClientError(null)
    const port = Number.parseInt(srvPort, 10) || 24800
    const next = await api("/api/start", { mode: "server", port, edge })
    setStatus(next)
  }

  const handleStartClient = async () => {
    const host = cliHost.trim()
    if (!host) {
      setClientError("Lütfen Mac (Server) IP adresini girin.")
      return
    }
    setClientError(null)
    const port = Number.parseInt(cliPort, 10) || 24800
    const next = await api("/api/start", {
      mode: "client",
      host,
      port,
      map_cmd_ctrl: mapCmdCtrl,
    })
    setStatus(next)
  }

  const handleStop = async () => {
    const next = await api("/api/stop", {})
    setStatus(next)
  }

  const handleToggle = async () => {
    const next = await api("/api/toggle", {})
    setStatus(next)
  }

  const handleTestMouse = async () => {
    const next = await api("/api/test-mouse", {})
    setStatus(next)
  }

  const handleOpenAccessibility = async () => {
    const next = await api("/api/open-accessibility", {})
    setStatus(next)
  }

  const handleSendFiles = async (files: FileList | File[]) => {
    const list = Array.from(files)
    for (const file of list) {
      setSendingFile(file.name)
      try {
        const buf = await file.arrayBuffer()
        const bytes = new Uint8Array(buf)
        let binary = ""
        const chunk = 0x8000
        for (let i = 0; i < bytes.length; i += chunk) {
          binary += String.fromCharCode(...bytes.subarray(i, i + chunk))
        }
        const dataB64 = btoa(binary)
        const next = await api("/api/send-file", {
          name: file.name,
          data: dataB64,
        })
        setStatus(next)
      } catch {
        // ignore single file failure
      } finally {
        setSendingFile(null)
      }
    }
  }

  const running = status.running
  const canControlClient =
    running && status.mode === "server" && status.client_connected
  const isRemote = canControlClient && status.remote_active
  const isWaiting = running && status.mode === "server" && !status.client_connected
  const showPermAlert =
    status.platform === "darwin" && !status.accessibility_trusted

  const statusText = !running
    ? "Sunucu Kapalı"
    : status.mode === "client"
      ? "Client Çalışıyor"
      : isWaiting
        ? "Windows Bekleniyor..."
        : isRemote
          ? "Kontrol: WINDOWS"
          : "Kontrol: MAC (Windows Bağlı)"

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-background text-foreground">
        <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,rgba(59,130,246,0.12),transparent_55%),radial-gradient(ellipse_at_bottom_right,rgba(16,185,129,0.08),transparent_50%)]" />

        <main className="mx-auto flex w-full max-w-4xl flex-col gap-5 px-4 py-8 sm:px-6">
          {/* Header */}
          <header className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex size-11 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-lg shadow-blue-500/25">
                <Keyboard className="size-5" />
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight">ES-Share</h1>
                <p className="text-xs text-muted-foreground">
                  Tek Klavye &amp; Fare ile Mac ↔ Windows Kontrolü
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {status.platform === "darwin" && (
                <Badge
                  variant="outline"
                  className={cn(
                    "gap-1.5 px-2.5 py-1",
                    status.accessibility_trusted
                      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-500 dark:text-emerald-400"
                      : "border-destructive/40 bg-destructive/10 text-destructive"
                  )}
                >
                  <ShieldCheck className="size-3.5" />
                  {status.accessibility_trusted
                    ? "Erişilebilirlik ✓"
                    : "İzin Eksik"}
                </Badge>
              )}

              <Badge
                variant="outline"
                className="gap-2 rounded-full bg-card/80 px-3 py-1 text-xs font-semibold backdrop-blur"
              >
                <span
                  className={cn(
                    "size-2 rounded-full",
                    !running
                      ? "bg-muted-foreground"
                      : isRemote
                        ? "animate-pulse bg-amber-400 shadow-[0_0_8px_#fbbf24]"
                        : isWaiting
                          ? "animate-pulse bg-sky-400 shadow-[0_0_8px_#38bdf8]"
                          : "bg-emerald-400 shadow-[0_0_8px_#34d399]"
                  )}
                />
                {statusText}
              </Badge>

              <Button
                variant="outline"
                size="icon"
                onClick={toggleTheme}
                aria-label={isDark ? "Aydınlık temaya geç" : "Karanlık temaya geç"}
              >
                {isDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
              </Button>
            </div>
          </header>

          {/* macOS Accessibility Warning */}
          {showPermAlert && (
            <Alert variant="destructive" className="border-destructive/50 bg-destructive/10">
              <AlertTriangle className="size-4" />
              <AlertTitle>macOS Erişilebilirlik İzni Eksik!</AlertTitle>
              <AlertDescription>
                İzin verilmeden klavye/fare yakalanamaz ve Mac imleci kilitlenemez.
                Erişilebilirlik ayarlarında hem <strong>Terminal</strong> hem de{" "}
                <strong>Python.app</strong> izinlerinin açık olduğundan emin olun.
              </AlertDescription>
              <AlertAction>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={handleOpenAccessibility}
                >
                  Erişilebilirlik Ayarlarını Aç
                </Button>
              </AlertAction>
            </Alert>
          )}

          {/* Main Tabs */}
          <Tabs
            value={tab}
            onValueChange={(v) => setTab(v as "server" | "client")}
            className="w-full"
          >
            <TabsList className="grid h-11 w-full grid-cols-2 p-1">
              <TabsTrigger value="server" className="gap-2">
                <Laptop className="size-4" />
                Mac — Ana Bilgisayar (Server)
              </TabsTrigger>
              <TabsTrigger value="client" className="gap-2">
                <Monitor className="size-4" />
                Windows — Bağlanan Cihaz (Client)
              </TabsTrigger>
            </TabsList>

            {/* SERVER TAB */}
            <TabsContent value="server" className="mt-3 flex flex-col gap-4">
              <Card className="bg-card/80 backdrop-blur">
                <CardHeader className="pb-0">
                  <CardDescription className="text-xs uppercase tracking-wider">
                    Mac Yerel IP Adresi (Windows&apos;a bunu girin)
                  </CardDescription>
                  <CardTitle className="flex items-center gap-2 font-mono text-2xl font-bold text-blue-500 dark:text-blue-400">
                    <Wifi className="size-5 text-blue-500/80 dark:text-blue-400/80" />
                    {status.local_ips.join(", ")}
                  </CardTitle>
                  <CardAction>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={handleCopyIp}
                      className="gap-1.5"
                    >
                      {copied ? (
                        <>
                          <Check className="size-3.5 text-emerald-500" />
                          Kopyalandı
                        </>
                      ) : (
                        <>
                          <Copy className="size-3.5" />
                          IP Kopyala
                        </>
                      )}
                    </Button>
                  </CardAction>
                </CardHeader>

                <CardContent className="flex flex-col gap-4 pt-2">
                  {/* Visual Desk & Dual-Display Canvas */}
                  <DeskCanvas
                    running={running}
                    clientConnected={status.client_connected}
                    remoteActive={status.remote_active}
                    edge={edge}
                    screenSize={status.screen_size}
                    onToggleRemote={handleToggle}
                    onSwapEdge={handleSwapEdge}
                    onSendFiles={(files) => void handleSendFiles(files)}
                    sendingFile={sendingFile}
                  />

                  {/* Settings */}
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="flex flex-col gap-2">
                      <Label htmlFor="edge-select">Ekran Kenarı Geçişi</Label>
                      <Select
                        value={edge}
                        onValueChange={(v) =>
                          v && void handleEdgeChange(v as EdgeOption)
                        }
                      >
                        <SelectTrigger id="edge-select" className="h-9 w-full">
                          <SelectValue>{EDGE_LABELS[edge]}</SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="right">
                            Sağ Kenar (Windows sağda)
                          </SelectItem>
                          <SelectItem value="left">
                            Sol Kenar (Windows solda)
                          </SelectItem>
                          <SelectItem value="none">
                            Kapalı (Sadece Kısayol)
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="flex flex-col gap-2">
                      <Label htmlFor="srv-port">Port</Label>
                      <Input
                        id="srv-port"
                        type="number"
                        min={1024}
                        max={65535}
                        value={srvPort}
                        onChange={(e) => setSrvPort(e.target.value)}
                        className="h-9 font-mono"
                      />
                    </div>
                  </div>

                  <Separator />

                  {/* Action Buttons */}
                  <div className="flex flex-wrap items-center gap-2.5">
                    <Button
                      onClick={handleStartServer}
                      disabled={running}
                      size="lg"
                      className="gap-2 bg-blue-600 text-white hover:bg-blue-500"
                    >
                      <Play className="size-4" />
                      Sunucuyu Başlat
                    </Button>

                    <Button
                      onClick={handleStop}
                      disabled={!running}
                      variant="destructive"
                      size="lg"
                      className="gap-2"
                    >
                      <Square className="size-4" />
                      Durdur
                    </Button>

                    <Button
                      onClick={handleToggle}
                      disabled={!canControlClient}
                      size="lg"
                      className="gap-2 bg-amber-500 text-slate-950 hover:bg-amber-400"
                    >
                      <ArrowLeftRight className="size-4" />
                      {isRemote ? "Mac'e Dön" : "Windows'a Geç"}
                    </Button>

                    <Button
                      onClick={handleTestMouse}
                      disabled={!canControlClient}
                      variant="outline"
                      size="lg"
                      className="gap-2 border-emerald-500/40 text-emerald-500 hover:bg-emerald-500/10 dark:text-emerald-400"
                    >
                      <MousePointerClick className="size-4" />
                      Bağlantıyı Test Et (Fare Oynat)
                    </Button>
                  </div>
                </CardContent>

                <CardFooter className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <span>Geçiş Kısayolu:</span>
                    <KbdGroup>
                      <Kbd>Ctrl</Kbd>
                      <span>+</span>
                      <Kbd>Alt</Kbd>
                      <span>+</span>
                      <Kbd>S</Kbd>
                    </KbdGroup>
                  </div>
                  <div className="flex items-center gap-2">
                    <span>Acil Dönüş:</span>
                    <KbdGroup>
                      <Kbd>3×</Kbd>
                      <Kbd>Esc</Kbd>
                    </KbdGroup>
                  </div>
                </CardFooter>
              </Card>
            </TabsContent>

            {/* CLIENT TAB */}
            <TabsContent value="client" className="mt-3">
              <Card className="bg-card/80 backdrop-blur">
                <CardHeader>
                  <CardTitle>Windows İstemci Bağlantısı</CardTitle>
                  <CardDescription>
                    Bu modu Windows makinede çalıştırdığınızda Mac&apos;in yerel IP
                    adresini girerek bağlanın.
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="flex flex-col gap-2">
                      <Label htmlFor="cli-host">Mac (Server) IP Adresi</Label>
                      <Input
                        id="cli-host"
                        placeholder="Örn: 192.168.1.25"
                        value={cliHost}
                        onChange={(e) => {
                          setCliHost(e.target.value)
                          if (clientError) setClientError(null)
                        }}
                        className="h-9 font-mono"
                      />
                    </div>

                    <div className="flex flex-col gap-2">
                      <Label htmlFor="cli-port">Port</Label>
                      <Input
                        id="cli-port"
                        type="number"
                        min={1024}
                        max={65535}
                        value={cliPort}
                        onChange={(e) => setCliPort(e.target.value)}
                        className="h-9 font-mono"
                      />
                    </div>
                  </div>

                  {clientError && (
                    <Alert variant="destructive">
                      <AlertTriangle className="size-4" />
                      <AlertDescription>{clientError}</AlertDescription>
                    </Alert>
                  )}

                  <div className="flex items-center justify-between rounded-lg border border-border/70 bg-muted/30 px-3.5 py-2.5">
                    <div className="flex flex-col gap-0.5">
                      <Label htmlFor="cmd-ctrl-map" className="cursor-pointer">
                        Mac Cmd ↔ Windows Ctrl Eşlemesi
                      </Label>
                      <span className="text-xs text-muted-foreground">
                        Cmd+C / Cmd+V kısayollarını Windows&apos;ta Ctrl+C / Ctrl+V
                        olarak uygular
                      </span>
                    </div>
                    <Switch
                      id="cmd-ctrl-map"
                      checked={mapCmdCtrl}
                      onCheckedChange={setMapCmdCtrl}
                    />
                  </div>

                  <div className="flex flex-wrap gap-2.5">
                    <Button
                      onClick={handleStartClient}
                      disabled={running}
                      size="lg"
                      className="gap-2 bg-blue-600 text-white hover:bg-blue-500"
                    >
                      <Play className="size-4" />
                      Mac&apos;e Bağlan
                    </Button>
                    <Button
                      onClick={handleStop}
                      disabled={!running}
                      variant="destructive"
                      size="lg"
                      className="gap-2"
                    >
                      <Square className="size-4" />
                      Bağlantıyı Kes
                    </Button>
                  </div>

                  <Separator />

                  {/* Client -> Mac Drag & Drop File Transfer */}
                  <div
                    onDragOver={(e) => {
                      if (!running || status.mode !== "client") return
                      e.preventDefault()
                      setDragOverMac(true)
                    }}
                    onDragLeave={() => setDragOverMac(false)}
                    onDrop={(e) => {
                      e.preventDefault()
                      setDragOverMac(false)
                      if (
                        running &&
                        status.mode === "client" &&
                        e.dataTransfer.files.length > 0
                      ) {
                        void handleSendFiles(e.dataTransfer.files)
                      }
                    }}
                    className={cn(
                      "flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-5 text-center transition-all",
                      dragOverMac
                        ? "border-emerald-400 bg-emerald-500/10"
                        : "border-border/70 bg-muted/20"
                    )}
                  >
                    <Upload className="size-5 text-blue-400" />
                    <div className="text-sm font-medium">
                      Mac&apos;e Dosya / Görsel Gönder
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Dosyaları buraya sürükleyip bırakın veya seçin (Mac&apos;te{" "}
                      <code>Downloads/ES-Share</code> klasörüne kaydedilir)
                    </p>
                    <input
                      ref={clientFileInputRef}
                      type="file"
                      multiple
                      className="hidden"
                      onChange={(e) => {
                        if (e.target.files && e.target.files.length > 0) {
                          void handleSendFiles(e.target.files)
                          e.target.value = ""
                        }
                      }}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={!running || status.mode !== "client" || Boolean(sendingFile)}
                      onClick={() => clientFileInputRef.current?.click()}
                      className="mt-1 gap-1.5"
                    >
                      <Upload className="size-3.5" />
                      {sendingFile ? `Gönderiliyor: ${sendingFile}` : "Dosya Seç"}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

          {/* Live Logs */}
          <Card className="bg-card/80 backdrop-blur" size="sm">
            <CardHeader className="border-b border-border/60 pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <Terminal className="size-4 text-muted-foreground" />
                Canlı Durum &amp; Günlük
              </CardTitle>
              <CardAction>
                <Badge variant="secondary" className="max-w-[340px] truncate font-normal">
                  {status.logs[status.logs.length - 1] ?? "Hazır"}
                </Badge>
              </CardAction>
            </CardHeader>
            <CardContent className="pt-3">
              <ScrollArea className="h-44 w-full rounded-lg border border-border/60 bg-background/80 p-3">
                <div className="flex flex-col gap-1 font-mono text-xs text-muted-foreground">
                  {status.logs.map((line, idx) => (
                    <div key={`${idx}-${line.slice(0, 12)}`} className="leading-relaxed">
                      {line}
                    </div>
                  ))}
                  <div ref={logEndRef} />
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </main>
      </div>
    </TooltipProvider>
  )
}

export default App

