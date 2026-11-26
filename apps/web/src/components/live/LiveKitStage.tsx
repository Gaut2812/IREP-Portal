"use client";

/**
 * Screen 07 stage on LiveKit (open source): audio, video and screen share inside the portal.
 * The API mints the token (room and rights); attendance comes from LiveKit's webhooks, so
 * nothing here reports presence. Students join with camera and mic off (bandwidth).
 */
import React, { useEffect, useReducer, useRef, useState } from "react";
import {
  ConnectionQuality, ConnectionState, Participant, RemoteParticipant, Room, RoomEvent, Track, VideoPresets,
} from "livekit-client";
import {
  Hand, Mic, MicOff, MonitorUp, MonitorX, UserX, Video, VideoOff, Volume2, WifiOff, Headphones,
} from "lucide-react";

type T = (key: string) => string;

export interface LiveKitStageProps {
  wsUrl: string;
  token: string;
  isTrainer: boolean;
  canShare: boolean;
  shareGrants: string[];
  t: T;
  onModerate: (userId: string, action: "mute" | "remove" | "grant_share" | "revoke_share") => Promise<void>;
  onToast: (msg: string) => void;
  onDisconnected: () => void;
}

const AVATAR = ["bg-brand", "bg-teal", "bg-violet", "bg-warning-fill", "bg-pink-600"];
const encoder = new TextEncoder();
const decoder = new TextDecoder();

function roleOf(p: Participant): "trainer" | "student" {
  try { return JSON.parse(p.metadata || "{}").role === "trainer" ? "trainer" : "student"; } catch { return "student"; }
}
function initialsOf(p: Participant): string {
  try {
    const i = JSON.parse(p.metadata || "{}").initials;
    if (i) return i;
  } catch { /* fall through */ }
  return (p.name || p.identity).split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
}

function VideoView({ track, mirror, fit = "cover", testId }: { track?: Track; mirror?: boolean; fit?: "cover" | "contain"; testId?: string }) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || !track) return;
    track.attach(el);
    return () => { track.detach(el); };
  }, [track]);
  return (
    <video ref={ref} autoPlay playsInline muted data-testid={testId}
      className={`w-full h-full ${fit === "contain" ? "object-contain" : "object-cover"} ${mirror ? "-scale-x-100" : ""}`} />
  );
}

function AudioSink({ track }: { track: Track }) {
  const ref = useRef<HTMLAudioElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    track.attach(el);
    return () => { track.detach(el); };
  }, [track]);
  return <audio ref={ref} autoPlay />;
}

const newRoom = () => new Room({
  adaptiveStream: true,       // subscribe only at the size a tile is drawn
  dynacast: true,             // stop sending layers nobody watches
  videoCaptureDefaults: { resolution: VideoPresets.h540.resolution },
  publishDefaults: { simulcast: true },
});

export function LiveKitStage(props: LiveKitStageProps) {
  // One Room per connect effect: React runs effects twice in development (Strict Mode), and a
  // Room reused across that cleanup would be disconnected by the first run's cleanup.
  const [room, setRoom] = useState<Room | null>(null);
  const { wsUrl, token, isTrainer, t, onToast, onDisconnected } = props;
  const [state, setState] = useState<ConnectionState>(ConnectionState.Connecting);
  const [needsAudioClick, setNeedsAudioClick] = useState(false);
  const [, bump] = useReducer((n: number) => n + 1, 0);
  const [hands, setHands] = useState<Set<string>>(new Set());
  const myHand = useRef(false);

  useEffect(() => {
    const r = newRoom();
    let cancelled = false;
    const sendHand = (up: boolean) => r.localParticipant.publishData(encoder.encode(JSON.stringify({ t: "hand", up })), { reliable: true }).catch(() => undefined);
    const onData = (payload: Uint8Array, p?: RemoteParticipant) => {
      if (!p) return;
      try {
        const msg = JSON.parse(decoder.decode(payload));
        if (msg.t === "hand") setHands((h) => { const n = new Set(h); if (msg.up) n.add(p.identity); else n.delete(p.identity); return n; });
      } catch { /* not ours */ }
    };
    const onJoin = () => { bump(); if (myHand.current) sendHand(true); };          // late joiners see raised hands
    const onLeave = (p: RemoteParticipant) => { setHands((h) => { const n = new Set(h); n.delete(p.identity); return n; }); bump(); };
    const onState = (s: ConnectionState) => { if (!cancelled) { setState(s); bump(); } };
    const onAudio = () => setNeedsAudioClick(!r.canPlaybackAudio);
    const onGone = () => { if (!cancelled) onDisconnected(); };

    r.on(RoomEvent.ConnectionStateChanged, onState)
      .on(RoomEvent.ParticipantConnected, onJoin)
      .on(RoomEvent.ParticipantDisconnected, onLeave)
      .on(RoomEvent.DataReceived, onData)
      .on(RoomEvent.AudioPlaybackStatusChanged, onAudio)
      .on(RoomEvent.Disconnected, onGone);
    for (const ev of [RoomEvent.TrackSubscribed, RoomEvent.TrackUnsubscribed, RoomEvent.TrackMuted, RoomEvent.TrackUnmuted,
      RoomEvent.LocalTrackPublished, RoomEvent.LocalTrackUnpublished, RoomEvent.ActiveSpeakersChanged,
      RoomEvent.ConnectionQualityChanged, RoomEvent.ParticipantPermissionsChanged, RoomEvent.TrackPublished, RoomEvent.TrackUnpublished]) {
      r.on(ev, bump);
    }
    setRoom(r);
    setState(ConnectionState.Connecting);

    (async () => {
      try {
        await r.connect(wsUrl, token);
        if (cancelled) return;
        setNeedsAudioClick(!r.canPlaybackAudio);
        if (isTrainer) {
          try { await r.localParticipant.enableCameraAndMicrophone(); } catch { if (!cancelled) onToast(t("live_class.lk_media_denied")); }
        }
        bump();
      } catch {
        if (!cancelled) { setState(ConnectionState.Disconnected); onToast(t("live_class.lk_connect_failed")); }
      }
    })();

    return () => {
      cancelled = true;
      r.removeAllListeners();
      r.disconnect();
    };
    // the token is fixed for this mount; t and callbacks may change identity without needing a reconnect
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsUrl, token]);

  if (!room) {
    return (
      <div className="flex-1 flex items-center justify-center" data-testid="lk-stage" data-state={ConnectionState.Connecting}>
        <div role="status" className="text-caption px-3 py-1.5 rounded-tile bg-warning-soft text-warning font-semibold">{t("live_class.lk_connecting")}</div>
      </div>
    );
  }
  return <StageView {...props} room={room} state={state} hands={hands} setHands={setHands} myHand={myHand}
    needsAudioClick={needsAudioClick} setNeedsAudioClick={setNeedsAudioClick} bump={bump} />;
}

interface StageViewProps extends LiveKitStageProps {
  room: Room;
  state: ConnectionState;
  hands: Set<string>;
  setHands: React.Dispatch<React.SetStateAction<Set<string>>>;
  myHand: React.MutableRefObject<boolean>;
  needsAudioClick: boolean;
  setNeedsAudioClick: (v: boolean) => void;
  bump: () => void;
}

function StageView({ room, state, hands, setHands, myHand, needsAudioClick, setNeedsAudioClick, bump,
  isTrainer, canShare, shareGrants, t, onModerate, onToast }: StageViewProps) {
  const [audioOnly, setAudioOnly] = useState(false);
  // audio-only: stop receiving other people's cameras (screen share stays)
  const remotes = Array.from(room.remoteParticipants.values());
  useEffect(() => {
    for (const p of room.remoteParticipants.values()) {
      const pub = p.getTrackPublication(Track.Source.Camera);
      if (pub && "setSubscribed" in pub) (pub as { setSubscribed: (s: boolean) => void }).setSubscribed(!audioOnly);
    }
  });

  const local = room.localParticipant;
  const everyone: Participant[] = [local, ...remotes];
  const camTrack = (p: Participant) => {
    const pub = p.getTrackPublication(Track.Source.Camera);
    return pub && !pub.isMuted ? pub.track : undefined;
  };
  const screenOwner = everyone.find((p) => p.getTrackPublication(Track.Source.ScreenShare)?.track);
  const trainerP = everyone.find((p) => roleOf(p) === "trainer");
  const main = screenOwner
    ? { p: screenOwner, track: screenOwner.getTrackPublication(Track.Source.ScreenShare)?.track, screen: true }
    : trainerP ? { p: trainerP, track: camTrack(trainerP), screen: false } : null;
  const strip = everyone.filter((p) => main?.screen || p !== main?.p);
  const STRIP_MAX = 12;
  const audioTracks = remotes.flatMap((p) => {
    const out: Track[] = [];
    for (const src of [Track.Source.Microphone, Track.Source.ScreenShareAudio]) {
      const tr = p.getTrackPublication(src)?.track;
      if (tr) out.push(tr);
    }
    return out;
  });

  const shareAllowed = isTrainer || canShare;
  const toggle = async (what: "mic" | "cam" | "screen") => {
    try {
      if (what === "mic") await local.setMicrophoneEnabled(!local.isMicrophoneEnabled);
      if (what === "cam") { await local.setCameraEnabled(!local.isCameraEnabled); if (!local.isCameraEnabled) setAudioOnly(false); }
      if (what === "screen") await local.setScreenShareEnabled(!local.isScreenShareEnabled, { audio: true });
    } catch (err: unknown) {
      const name = (err as { name?: string })?.name;
      onToast(name === "NotAllowedError" ? t("live_class.lk_media_denied") : what === "screen" && !shareAllowed ? t("live_class.lk_share_not_allowed") : t("live_class.action_failed"));
    }
    bump();
  };
  const toggleHand = () => {
    myHand.current = !myHand.current;
    setHands((h) => { const n = new Set(h); if (myHand.current) n.add(local.identity); else n.delete(local.identity); return n; });
    room.localParticipant.publishData(encoder.encode(JSON.stringify({ t: "hand", up: myHand.current })), { reliable: true }).catch(() => undefined);
  };
  const toggleAudioOnly = async () => {
    const next = !audioOnly;
    setAudioOnly(next);
    if (next && local.isCameraEnabled) { try { await local.setCameraEnabled(false); } catch { /* ignore */ } }
    bump();
  };

  const poor = local.connectionQuality === ConnectionQuality.Poor || local.connectionQuality === ConnectionQuality.Lost;
  const label = (p: Participant) => `${p.name || p.identity}${p === local ? ` (${t("live_class.you")})` : roleOf(p) === "trainer" ? ` (${t("live_class.trainer")})` : ""}`;

  const tile = (p: Participant, i: number) => {
    const v = camTrack(p);
    const muted = !p.isMicrophoneEnabled;
    const isStudent = roleOf(p) === "student";
    const granted = shareGrants.includes(p.identity);
    return (
      <div key={p.identity} className={`relative w-40 h-24 flex-shrink-0 rounded-tile overflow-hidden bg-[#0F172A] border ${p.isSpeaking ? "border-teal" : "border-[#2D3748]"}`}
        data-testid="lk-tile" data-identity={p.identity}>
        {v && !(audioOnly && p !== local) ? <VideoView track={v} mirror={p === local} /> : (
          <div className="w-full h-full flex items-center justify-center">
            <span className={`w-10 h-10 rounded-full ${AVATAR[i % AVATAR.length]} text-white font-semibold text-xs flex items-center justify-center`}>{initialsOf(p)}</span>
          </div>
        )}
        <div className="absolute bottom-0 inset-x-0 px-1.5 py-0.5 bg-black/60 flex items-center gap-1 text-caption">
          {muted ? <MicOff className="w-3 h-3 text-red-400 flex-shrink-0" /> : <Mic className="w-3 h-3 text-teal flex-shrink-0" />}
          <span className="truncate text-line">{label(p)}</span>
          {hands.has(p.identity) && <Hand className="w-3 h-3 text-amber-400 flex-shrink-0 ml-auto" aria-label={t("live_class.lk_hand_raised")} />}
        </div>
        {isTrainer && p !== local && isStudent && (
          <div className="absolute top-1 right-1 flex gap-1">
            {!muted && (
              <button onClick={() => onModerate(p.identity, "mute")} aria-label={`${t("live_class.lk_mute_participant")} ${p.name}`} title={t("live_class.lk_mute_participant")}
                className="p-1 rounded bg-black/70 text-line hover:text-white" data-testid="lk-mute"><MicOff className="w-3 h-3" /></button>
            )}
            <button onClick={() => onModerate(p.identity, granted ? "revoke_share" : "grant_share")}
              aria-label={`${granted ? t("live_class.lk_revoke_share") : t("live_class.lk_allow_share")} ${p.name}`} title={granted ? t("live_class.lk_revoke_share") : t("live_class.lk_allow_share")}
              aria-pressed={granted} className={`p-1 rounded bg-black/70 hover:text-white ${granted ? "text-teal" : "text-line"}`} data-testid="lk-share-grant">
              {granted ? <MonitorX className="w-3 h-3" /> : <MonitorUp className="w-3 h-3" />}
            </button>
            <button onClick={() => { if (window.confirm(`${t("live_class.lk_remove_confirm")} ${p.name}?`)) onModerate(p.identity, "remove"); }}
              aria-label={`${t("live_class.lk_remove")} ${p.name}`} title={t("live_class.lk_remove")}
              className="p-1 rounded bg-black/70 text-red-400 hover:text-white" data-testid="lk-remove"><UserX className="w-3 h-3" /></button>
          </div>
        )}
      </div>
    );
  };

  const btn = (on: boolean, extra = "") => `p-2 rounded-tile ${on ? "bg-teal text-white" : "bg-[#1E293B] text-subtle hover:text-white"} disabled:opacity-40 disabled:cursor-not-allowed ${extra}`;

  return (
    <div className="flex-1 flex flex-col gap-2 overflow-hidden min-h-0" data-testid="lk-stage" data-state={state}>
      {audioTracks.map((tr) => <AudioSink key={tr.sid ?? tr.mediaStreamTrack?.id} track={tr} />)}

      {(state === ConnectionState.Connecting || state === ConnectionState.Reconnecting || state === ConnectionState.SignalReconnecting) && (
        <div role="status" className="text-caption px-3 py-1.5 rounded-tile bg-warning-soft text-warning font-semibold" data-testid="lk-connecting">
          {state === ConnectionState.Connecting ? t("live_class.lk_connecting") : t("live_class.lk_reconnecting")}
        </div>
      )}
      {state === ConnectionState.Connected && poor && (
        <div role="status" className="text-caption px-3 py-1.5 rounded-tile bg-warning-soft text-warning font-semibold flex items-center gap-1.5" data-testid="lk-poor">
          <WifiOff className="w-3.5 h-3.5" /> {t("live_class.lk_poor_network")}
        </div>
      )}
      {needsAudioClick && (
        <button onClick={() => room.startAudio().then(() => setNeedsAudioClick(false))}
          className="text-xs px-3 py-2 rounded-tile bg-brand text-white font-semibold flex items-center gap-1.5 self-start" data-testid="lk-enable-audio">
          <Volume2 className="w-3.5 h-3.5" /> {t("live_class.lk_enable_audio")}
        </button>
      )}

      {/* main view: screen share, else the trainer's camera */}
      <div className="flex-1 relative rounded-card overflow-hidden bg-[#0B0F19] border border-[#2D3748] min-h-0" data-testid="lk-main">
        {main?.track ? (
          <VideoView track={main.track} fit={main.screen ? "contain" : "cover"} mirror={!main.screen && main.p === local} testId="lk-main-video" />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center gap-2 text-center p-4">
            {main && <span className="w-16 h-16 rounded-full bg-teal text-white font-semibold text-base flex items-center justify-center">{initialsOf(main.p)}</span>}
            <p className="text-xs text-subtle">{main ? t("live_class.lk_no_video") : t("live_class.lk_waiting_trainer")}</p>
          </div>
        )}
        {main && (
          <span className="absolute left-2 top-2 text-caption px-2 py-0.5 rounded bg-black/70 text-line font-semibold">
            {main.screen ? `${main.p.name || main.p.identity} · ${t("live_class.lk_screen")}` : label(main.p)}
          </span>
        )}
      </div>

      {/* filmstrip */}
      <div className="flex gap-2 overflow-x-auto pb-1 flex-shrink-0" data-testid="lk-strip">
        {strip.slice(0, STRIP_MAX).map(tile)}
        {strip.length > STRIP_MAX && <span className="self-center text-caption text-subtle px-2">+{strip.length - STRIP_MAX}</span>}
      </div>

      {/* own controls */}
      <div className="flex items-center gap-2 flex-shrink-0" data-testid="lk-controls">
        <button onClick={() => toggle("mic")} disabled={state !== ConnectionState.Connected} aria-pressed={local.isMicrophoneEnabled}
          aria-label={local.isMicrophoneEnabled ? t("live_class.mute") : t("live_class.unmute")} className={btn(local.isMicrophoneEnabled)} data-testid="lk-mic">
          {local.isMicrophoneEnabled ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4" />}
        </button>
        <button onClick={() => toggle("cam")} disabled={state !== ConnectionState.Connected} aria-pressed={local.isCameraEnabled}
          aria-label={t("live_class.camera")} className={btn(local.isCameraEnabled)} data-testid="lk-cam">
          {local.isCameraEnabled ? <Video className="w-4 h-4" /> : <VideoOff className="w-4 h-4" />}
        </button>
        <button onClick={() => toggle("screen")} disabled={state !== ConnectionState.Connected || !shareAllowed} aria-pressed={local.isScreenShareEnabled}
          aria-label={local.isScreenShareEnabled ? t("live_class.lk_stop_share") : t("live_class.lk_share_screen")}
          title={shareAllowed ? undefined : t("live_class.lk_share_not_allowed")} className={btn(local.isScreenShareEnabled)} data-testid="lk-screen">
          {local.isScreenShareEnabled ? <MonitorX className="w-4 h-4" /> : <MonitorUp className="w-4 h-4" />}
        </button>
        <button onClick={toggleHand} disabled={state !== ConnectionState.Connected} aria-pressed={hands.has(local.identity)}
          aria-label={t("live_class.raise_hand")} className={btn(false, hands.has(local.identity) ? "!bg-warning-fill !text-white" : "")} data-testid="lk-hand">
          <Hand className="w-4 h-4" />
        </button>
        <button onClick={toggleAudioOnly} aria-pressed={audioOnly} aria-label={t("live_class.lk_audio_only")} title={t("live_class.lk_audio_only")}
          className={btn(audioOnly)} data-testid="lk-audio-only">
          <Headphones className="w-4 h-4" />
        </button>
        <span className="text-caption text-subtle ml-1 hidden md:inline">{audioOnly ? t("live_class.lk_audio_only_on") : ""}</span>
        {isTrainer && hands.size > 0 && (
          <span className="ml-auto text-caption text-amber-400 font-semibold flex items-center gap-1" data-testid="lk-hands-count">
            <Hand className="w-3.5 h-3.5" /> {hands.size}
          </span>
        )}
      </div>
    </div>
  );
}

export default LiveKitStage;
