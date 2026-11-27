import { useRef, useState } from "react"
import {
  ArrowLeftRight,
  ClipboardCheck,
  Keyboard,
  Mouse,
  MousePointer2,
  Sparkles,
  Upload,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

export type EdgeOption = "right" | "left" | "none"

interface DeskCanvasProps {
  running: boolean
  clientConnected: boolean
  remoteActive: boolean
  edge: EdgeOption
  screenSize: [number, number]
  onToggleRemote: () => void
  onSwapEdge: () => void
  onSendFiles?: (files: FileList | File[]) => void
  sendingFile?: string | null
}

export function DeskCanvas({
  running,
  clientConnected,
  remoteActive,
  edge,
  screenSize,
  onToggleRemote,
  onSwapEdge,
  onSendFiles,
  sendingFile,
}: DeskCanvasProps) {
  const [dragOverWin, setDragOverWin] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const canSwitch = running && clientConnected
  const macActive = !canSwitch || !remoteActive
  const winActive = canSwitch && remoteActive

  const macDisplay = (
    <div
      key="desk-mac"
      style={{ viewTransitionName: "desk-mac" }}
      className="desk-display flex flex-col items-center gap-2"
    >
      <Tooltip>
        <TooltipTrigger
          render={
            <button
              type="button"
              disabled={!canSwitch || macActive}
              onClick={() => {
                if (canSwitch && remoteActive) onToggleRemote()
              }}
              aria-label="Mac ekranı"
              className={cn(
                "group relative w-full max-w-[300px] rounded-xl text-left transition-all outline-none focus-visible:ring-2 focus-visible:ring-ring",
                canSwitch && remoteActive
                  ? "cursor-pointer hover:scale-[1.015]"
                  : "cursor-default"
              )}
            />
          }
        >
          {/* MacBook Lid / Bezel */}
          <div
            className={cn(
              "relative overflow-hidden rounded-t-xl border-2 bg-zinc-950 p-1.5 shadow-xl transition-all",
              macActive
                ? "border-emerald-400/80 shadow-emerald-500/20 ring-4 ring-emerald-500/15"
                : "border-border/80 opacity-80 group-hover:opacity-100"
            )}
          >
            <div className="mx-auto mb-1 flex h-2 w-12 items-center justify-center rounded-b-md bg-zinc-900">
              <span className="size-1 rounded-full bg-zinc-700" />
            </div>

            <div className="relative flex aspect-[16/10] w-full flex-col justify-between overflow-hidden rounded-md bg-[radial-gradient(circle_at_25%_20%,#34d399_0%,#0ea5e9_42%,#312e81_100%)] p-2.5 text-white">
              <div className="flex items-center justify-between rounded-sm bg-black/35 px-2 py-0.5 text-[10px] backdrop-blur-sm">
                <div className="flex items-center gap-1">
                  <span className="size-1.5 rounded-full bg-rose-400" />
                  <span className="size-1.5 rounded-full bg-amber-300" />
                  <span className="size-1.5 rounded-full bg-emerald-400" />
                </div>
                <span className="font-mono text-[9px] text-white/85">
                  {screenSize[0]}×{screenSize[1]}
                </span>
              </div>

              <div className="flex flex-col items-center justify-center gap-1 py-1">
                <Badge
                  className={cn(
                    "border text-[10px] font-semibold backdrop-blur-md",
                    macActive
                      ? "border-emerald-300/60 bg-emerald-500/30 text-white"
                      : "border-white/25 bg-black/40 text-white/80"
                  )}
                >
                  {!running ? "Ana PC" : macActive ? "AKTİF KONTROL" : "Beklemede"}
                </Badge>
                <span className="text-xs font-semibold tracking-tight drop-shadow">
                  macOS
                </span>
              </div>

              {macActive && (
                <div className="desk-cursor-animated pointer-events-none absolute right-5 bottom-6 flex items-center gap-1 rounded-full bg-black/55 px-1.5 py-0.5 text-[9px] text-emerald-300 shadow">
                  <MousePointer2 className="size-3 fill-emerald-400 text-white" />
                </div>
              )}

              <div className="mx-auto flex items-center gap-1 rounded-full bg-white/20 px-2 py-1 backdrop-blur-md">
                <span className="size-2 rounded-sm bg-sky-300" />
                <span className="size-2 rounded-sm bg-emerald-300" />
                <span className="size-2 rounded-sm bg-amber-300" />
                <span className="size-2 rounded-sm bg-violet-300" />
              </div>
            </div>
          </div>

          <div className="mx-auto h-2.5 w-[104%] -translate-x-[2%] rounded-b-lg border-x border-b border-zinc-400/30 bg-gradient-to-b from-zinc-300 to-zinc-500 dark:from-zinc-600 dark:to-zinc-800">
            <div className="mx-auto h-1 w-10 rounded-b bg-zinc-400/60 dark:bg-zinc-900/70" />
          </div>
        </TooltipTrigger>
        <TooltipContent>
          {canSwitch && remoteActive
            ? "Kontrolü Mac'e geri almak için tıklayın"
            : `Mac (Ana Bilgisayar) — ${screenSize[0]}×${screenSize[1]}`}
        </TooltipContent>
      </Tooltip>
    </div>
  )

  const winDisplay = (
    <div
      key="desk-win"
      style={{ viewTransitionName: "desk-win" }}
      className="desk-display flex flex-col items-center gap-2"
    >
      <Tooltip>
        <TooltipTrigger
          render={
            <button
              type="button"
              disabled={!canSwitch || winActive}
              onClick={() => {
                if (canSwitch && !remoteActive) onToggleRemote()
              }}
              aria-label="Windows ekranı"
              className={cn(
                "group relative w-full max-w-[300px] rounded-xl text-left transition-all outline-none focus-visible:ring-2 focus-visible:ring-ring",
                canSwitch && !remoteActive
                  ? "cursor-pointer hover:scale-[1.015]"
                  : "cursor-default"
              )}
            />
          }
        >
          {/* Desktop Monitor Frame (Drop Zone for Windows File Transfer) */}
          <div
            onDragOver={(e) => {
              if (!canSwitch || !onSendFiles) return
              e.preventDefault()
              setDragOverWin(true)
            }}
            onDragLeave={() => setDragOverWin(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragOverWin(false)
              if (canSwitch && onSendFiles && e.dataTransfer.files.length > 0) {
                onSendFiles(e.dataTransfer.files)
              }
            }}
            className={cn(
              "relative overflow-hidden rounded-xl border-2 bg-zinc-950 p-1.5 shadow-xl transition-all",
              dragOverWin
                ? "border-dashed border-emerald-400 ring-4 ring-emerald-500/30"
                : winActive
                  ? "border-amber-400/90 shadow-amber-500/25 ring-4 ring-amber-500/20"
                  : clientConnected
                    ? "border-sky-400/50"
                    : "border-border/70 opacity-75"
            )}
          >
            {dragOverWin && (
              <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-1 rounded-lg bg-emerald-950/85 text-xs font-semibold text-emerald-200 backdrop-blur-xs">
                <Upload className="size-5 text-emerald-300" />
                <span>Windows&apos;a Göndermek İçin Bırakın</span>
              </div>
            )}

            <div
              className={cn(
                "relative flex aspect-[16/10] w-full flex-col justify-between overflow-hidden rounded-md p-2.5 text-white transition-all",
                clientConnected
                  ? "bg-[radial-gradient(circle_at_60%_40%,#38bdf8_0%,#2563eb_45%,#0f172a_100%)]"
                  : "bg-[linear-gradient(135deg,#0f172a_0%,#1e293b_100%)]"
              )}
            >
              <div className="flex items-center justify-between text-[10px]">
                <span className="grid grid-cols-2 gap-0.5 opacity-80">
                  <span className="size-1.5 rounded-[1px] bg-sky-300" />
                  <span className="size-1.5 rounded-[1px] bg-sky-300" />
                  <span className="size-1.5 rounded-[1px] bg-sky-300" />
                  <span className="size-1.5 rounded-[1px] bg-sky-300" />
                </span>
                <span className="rounded bg-black/35 px-1.5 py-0.5 text-[9px] text-white/80">
                  {clientConnected ? "TCP Bağlı" : "Çevrimdışı"}
                </span>
              </div>

              <div className="flex flex-col items-center justify-center gap-1 py-1">
                <Badge
                  className={cn(
                    "border text-[10px] font-semibold backdrop-blur-md",
                    winActive
                      ? "border-amber-300/70 bg-amber-500/35 text-amber-50"
                      : clientConnected
                        ? "border-emerald-300/50 bg-emerald-500/25 text-emerald-50"
                        : "border-white/20 bg-black/40 text-white/75"
                  )}
                >
                  {winActive
                    ? "AKTİF KONTROL"
                    : clientConnected
                      ? "Bağlı ✓"
                      : running
                        ? "Bekleniyor..."
                        : "Kapalı"}
                </Badge>
                <span className="text-xs font-semibold tracking-tight drop-shadow">
                  Windows
                </span>
              </div>

              {winActive && (
                <div className="desk-cursor-animated pointer-events-none absolute right-5 bottom-6 flex items-center gap-1 rounded-full bg-black/60 px-1.5 py-0.5 text-[9px] text-amber-300 shadow">
                  <MousePointer2 className="size-3 fill-amber-400 text-white" />
                </div>
              )}

              <div className="mx-auto flex w-4/5 items-center justify-center gap-1.5 rounded-sm bg-black/45 px-2 py-1 backdrop-blur-md">
                <span className="size-2 rounded-[2px] bg-sky-400" />
                <span className="size-2 rounded-full bg-white/60" />
                <span className="size-2 rounded-[2px] bg-amber-300/80" />
                <span className="size-2 rounded-[2px] bg-emerald-300/80" />
              </div>
            </div>
          </div>

          <div className="mx-auto flex flex-col items-center">
            <div className="h-2.5 w-6 bg-gradient-to-b from-zinc-500 to-zinc-700 dark:from-zinc-700 dark:to-zinc-800" />
            <div className="h-1.5 w-20 rounded-full bg-zinc-400/70 shadow-sm dark:bg-zinc-700" />
          </div>
        </TooltipTrigger>
        <TooltipContent>
          {canSwitch && !remoteActive
            ? "Kontrolü Windows'a geçirmek için tıklayın (veya dosya sürükleyin)"
            : clientConnected
              ? "Windows (Bağlı Cihaz — dosya sürükleyip bırakabilirsiniz)"
              : "Windows istemcisi bekleniyor"}
        </TooltipContent>
      </Tooltip>
    </div>
  )

  const bridge = (
    <div
      key="desk-bridge"
      style={{ viewTransitionName: "desk-bridge" }}
      className="desk-display flex flex-col items-center justify-center gap-2 px-1"
    >
      <div
        className={cn(
          "hidden h-16 w-1 rounded-full sm:block",
          edge === "none"
            ? "bg-border/60"
            : winActive
              ? "desk-portal-animated bg-gradient-to-b from-amber-400 via-orange-400 to-amber-500 shadow-[0_0_12px_rgba(245,158,11,0.6)]"
              : clientConnected
                ? "desk-portal-animated bg-gradient-to-b from-emerald-400 via-sky-400 to-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.4)]"
                : "bg-border"
        )}
      />

      <Tooltip>
        <TooltipTrigger
          render={
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={onSwapEdge}
              aria-label="Ekran sırasını değiştir"
              className="rounded-full bg-card/90 shadow-sm hover:scale-105"
            />
          }
        >
          <ArrowLeftRight className="size-4" />
        </TooltipTrigger>
        <TooltipContent>
          {edge === "left"
            ? "Windows şu an solda — sağa almak için tıklayın"
            : edge === "right"
              ? "Windows şu an sağda — sola almak için tıklayın"
              : "Kenar geçişini etkinleştirmek için tıklayın"}
        </TooltipContent>
      </Tooltip>

      <span className="text-[11px] font-medium text-muted-foreground">
        {edge === "none"
          ? "Sadece Kısayol"
          : edge === "left"
            ? "Sol Kenar"
            : "Sağ Kenar"}
      </span>
    </div>
  )

  return (
    <div className="desk-stage relative rounded-2xl border border-border/80 bg-[radial-gradient(#94a3b826_1px,transparent_1px)] [background-size:16px_16px] p-4 sm:p-5">
      <div
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute inset-0 -z-10 rounded-2xl transition-opacity duration-300",
          winActive
            ? "bg-[radial-gradient(360px_circle_at_75%_45%,rgba(245,158,11,0.12),transparent_70%)]"
            : "bg-[radial-gradient(360px_circle_at_25%_45%,rgba(16,185,129,0.12),transparent_70%)]"
        )}
      />

      <div className="desk-grid">
        {edge === "left"
          ? [winDisplay, bridge, macDisplay]
          : [macDisplay, bridge, winDisplay]}
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-center gap-2 border-t border-border/60 pt-3">
        <div className="inline-flex items-center gap-2 rounded-full border border-border/80 bg-card/90 px-3.5 py-1.5 text-xs font-medium shadow-xs backdrop-blur">
          <Keyboard className="size-3.5 text-blue-400" />
          <Mouse className="size-3.5 text-blue-400" />
          <span>Tek Klavye &amp; Fare</span>
          <span className="text-muted-foreground">➔</span>
          <span
            className={cn(
              "inline-flex items-center gap-1 font-semibold",
              winActive ? "text-amber-400" : "text-emerald-400"
            )}
          >
            <Sparkles className="size-3" />
            {winActive ? "Windows'u Yönetiyor" : "Mac'i Yönetiyor"}
          </span>
        </div>

        <div className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-500 dark:text-emerald-400">
          <ClipboardCheck className="size-3.5" />
          <span>Ortak Pano ✓</span>
        </div>

        {onSendFiles && (
          <>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files.length > 0) {
                  onSendFiles(e.target.files)
                  e.target.value = ""
                }
              }}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!canSwitch || Boolean(sendingFile)}
              onClick={() => fileInputRef.current?.click()}
              className="h-8 gap-1.5 rounded-full"
            >
              <Upload className="size-3.5" />
              {sendingFile
                ? `Gönderiliyor: ${sendingFile}`
                : "Windows'a Dosya Gönder"}
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
