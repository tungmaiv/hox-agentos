// frontend/src/app/settings/channels/page.tsx
"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";

// -- Type interfaces for API responses --

interface PairResponse {
  code: string;
  expires_in: number;
}

interface ChannelAccountResponse {
  id: string;
  channel: string;
  external_user_id: string;
  display_name: string | null;
  is_paired: boolean;
}

interface ChannelInfoEntry {
  available: boolean;
  username?: string;
  display_name?: string;
}

// -- Channel configuration --

interface ChannelConfig {
  key: string;
  name: string;
  icon: string;
  pairingInstruction: (code: string, botUsername?: string) => string;
  setupInstructions: {
    agentOs: string[];
    platform: string[];
  };
}

const CHANNELS: ChannelConfig[] = [
  {
    key: "telegram",
    name: "Telegram",
    icon: "T",
    pairingInstruction: (code: string, botUsername?: string) =>
      `Send /pair ${code} to @${botUsername || "your bot"} on Telegram`,
    setupInstructions: {
      agentOs: [
        "Create a bot via @BotFather on Telegram and copy the bot token",
        "Set TELEGRAM_BOT_TOKEN in the Telegram gateway environment",
        "Set TELEGRAM_WEBHOOK_URL to point to your gateway's /webhook endpoint",
        "Start or restart the Telegram gateway service",
      ],
      platform: [
        "Open Telegram and search for your bot by username",
        "Start a conversation with the bot (press Start or send /start)",
        "Generate a pairing code above and send /pair <code> to the bot",
      ],
    },
  },
  {
    key: "whatsapp",
    name: "WhatsApp",
    icon: "W",
    pairingInstruction: (code: string) =>
      `Send /pair ${code} to the Blitz number on WhatsApp`,
    setupInstructions: {
      agentOs: [
        "Create a WhatsApp Business App in Meta Business Suite",
        "Set WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID in the WhatsApp gateway environment",
        "Set WHATSAPP_VERIFY_TOKEN for webhook verification",
        "Configure the webhook URL in Meta Business Suite to point to your gateway",
      ],
      platform: [
        "Open WhatsApp and message the configured business number",
        "Generate a pairing code above and send /pair <code> to the number",
      ],
    },
  },
  {
    key: "ms_teams",
    name: "Teams",
    icon: "M",
    pairingInstruction: (code: string) =>
      `Send /pair ${code} in a DM to Blitz Bot in Teams`,
    setupInstructions: {
      agentOs: [
        "Register a Bot in the Azure Bot Framework portal",
        "Set TEAMS_APP_ID and TEAMS_APP_PASSWORD in the Teams gateway environment",
        "Configure the messaging endpoint URL in Azure",
        "Start or restart the Teams gateway service",
      ],
      platform: [
        "Add the bot to your Teams workspace via the Apps catalog",
        "Open a direct message with the bot in Teams",
        "Generate a pairing code above and send /pair <code> to the bot",
      ],
    },
  },
];

// -- Countdown timer hook --

function useCountdown(initialSeconds: number, active: boolean) {
  const [remaining, setRemaining] = useState(initialSeconds);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!active) {
      setRemaining(initialSeconds);
      return;
    }
    setRemaining(initialSeconds);
    intervalRef.current = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          if (intervalRef.current) clearInterval(intervalRef.current);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [active, initialSeconds]);

  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  const display = `${minutes}:${seconds.toString().padStart(2, "0")}`;

  return { remaining, display };
}

// -- Toggle switch component --

function ToggleSwitch({
  enabled,
  onChange,
  disabled,
}: {
  enabled: boolean;
  onChange: (val: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      disabled={disabled}
      onClick={() => onChange(!enabled)}
      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${
        enabled ? "bg-blue-600" : "bg-gray-200"
      }`}
    >
      <span
        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
          enabled ? "translate-x-5" : "translate-x-0"
        }`}
      />
    </button>
  );
}

// -- Setup Guide component --

function SetupGuide({
  config,
  channelInfo,
}: {
  config: ChannelConfig;
  channelInfo?: ChannelInfoEntry;
}) {
  const [open, setOpen] = useState(false);

  // For Telegram, dynamically insert bot username into platform instructions
  const platformSteps = config.setupInstructions.platform.map((step) => {
    if (
      config.key === "telegram" &&
      channelInfo?.username &&
      step.includes("search for your bot by username")
    ) {
      return `Open Telegram and search for @${channelInfo.username}`;
    }
    return step;
  });

  return (
    <div className="mt-3 border-t border-gray-100 pt-2">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-gray-700 transition-colors w-full"
      >
        <svg
          className={`w-3.5 h-3.5 transition-transform ${open ? "rotate-90" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
        </svg>
        Setup Guide
      </button>

      {open && (
        <div className="mt-2 space-y-3">
          <div>
            <h4 className="text-xs font-semibold text-gray-700 mb-1">
              AgentOS Configuration
            </h4>
            <ol className="list-decimal list-inside text-xs text-gray-600 space-y-1 pl-1">
              {config.setupInstructions.agentOs.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          </div>
          <div>
            <h4 className="text-xs font-semibold text-gray-700 mb-1">
              Platform Setup
            </h4>
            <ol className="list-decimal list-inside text-xs text-gray-600 space-y-1 pl-1">
              {platformSteps.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          </div>
        </div>
      )}
    </div>
  );
}

// -- Channel Card component --

function ChannelCard({
  config,
  account,
  enabled,
  channelInfo,
  onToggle,
  onLink,
  onUnlink,
  onRefresh,
}: {
  config: ChannelConfig;
  account: ChannelAccountResponse | undefined;
  enabled: boolean;
  channelInfo?: ChannelInfoEntry;
  onToggle: (channel: string, val: boolean) => void;
  onLink: (channel: string) => Promise<void>;
  onUnlink: (accountId: string, channelName: string) => Promise<void>;
  onRefresh: () => Promise<void>;
}) {
  const [pairingCode, setPairingCode] = useState<string | null>(null);
  const [pairingActive, setPairingActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [confirmUnlink, setConfirmUnlink] = useState(false);
  const [copied, setCopied] = useState(false);

  const { remaining, display } = useCountdown(600, pairingActive);

  // When countdown reaches 0, expire the code
  useEffect(() => {
    if (pairingActive && remaining === 0) {
      setPairingActive(false);
      setPairingCode(null);
    }
  }, [pairingActive, remaining]);

  // Poll for pairing completion while code is active
  useEffect(() => {
    if (!pairingActive) return;
    const pollInterval = setInterval(() => {
      void onRefresh();
    }, 3000);
    return () => clearInterval(pollInterval);
  }, [pairingActive, onRefresh]);

  // Clear pairing state when account becomes paired
  useEffect(() => {
    if (pairingActive && account) {
      setPairingActive(false);
      setPairingCode(null);
    }
  }, [pairingActive, account]);

  const handleLink = async () => {
    setLoading(true);
    try {
      await onLink(config.key);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateCode = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/channels/pair", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel: config.key }),
      });
      if (res.ok) {
        const data = (await res.json()) as PairResponse;
        setPairingCode(data.code);
        setPairingActive(true);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleUnlink = async () => {
    if (!account) return;
    setLoading(true);
    try {
      await onUnlink(account.id, config.name);
      setConfirmUnlink(false);
    } finally {
      setLoading(false);
    }
  };

  const handleCancelPairing = () => {
    setPairingCode(null);
    setPairingActive(false);
  };

  const handleCopy = async () => {
    if (!pairingCode) return;
    try {
      await navigator.clipboard.writeText(pairingCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard API may not be available
    }
  };

  const isPaired = !!account;
  const displayName = account?.display_name || account?.external_user_id || "";

  return (
    <div
      className={`border rounded-lg p-5 transition-colors ${
        enabled
          ? "border-gray-200 bg-white"
          : "border-gray-100 bg-gray-50 opacity-60"
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div
            className={`w-10 h-10 rounded-lg flex items-center justify-center font-bold text-lg ${
              enabled
                ? "bg-blue-100 text-blue-700"
                : "bg-gray-200 text-gray-400"
            }`}
          >
            {config.icon}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-900">
              {config.name}
            </h3>
            {isPaired && enabled && (
              <p className="text-xs text-green-600 mt-0.5">
                Linked as {displayName}
              </p>
            )}
            {!enabled && (
              <p className="text-xs text-gray-400 mt-0.5">Disabled</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {isPaired && enabled && !confirmUnlink && (
            <button
              onClick={() => setConfirmUnlink(true)}
              className="px-3 py-1.5 text-xs font-medium text-red-600 border border-red-200 rounded-md hover:bg-red-50 transition-colors"
            >
              Unlink
            </button>
          )}
          <ToggleSwitch
            enabled={enabled}
            onChange={(val) => onToggle(config.key, val)}
          />
        </div>
      </div>

      {/* Confirmation dialog for unlink */}
      {confirmUnlink && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3 mb-3">
          <p className="text-sm text-red-700 mb-2">
            Are you sure you want to unlink {config.name}?
          </p>
          <div className="flex gap-2">
            <button
              onClick={handleUnlink}
              disabled={loading}
              className="px-3 py-1 text-xs font-medium text-white bg-red-600 rounded-md hover:bg-red-700 disabled:opacity-50"
            >
              {loading ? "Unlinking..." : "Yes, Unlink"}
            </button>
            <button
              onClick={() => setConfirmUnlink(false)}
              className="px-3 py-1 text-xs font-medium text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Link button and pairing code */}
      {!isPaired && !pairingCode && enabled && (
        <button
          onClick={handleGenerateCode}
          disabled={loading}
          className="w-full px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {loading ? "Generating..." : `Link ${config.name}`}
        </button>
      )}

      {/* Active pairing code with countdown */}
      {!isPaired && pairingCode && pairingActive && enabled && (
        <div className="bg-gray-50 border border-gray-200 rounded-md p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-gray-500">
              Pairing Code
            </span>
            <span className="text-xs text-gray-500">
              Code expires in {display}
            </span>
          </div>
          <div className="flex items-center justify-center gap-2 mb-2">
            <p className="text-2xl font-mono font-bold tracking-widest text-gray-900">
              {pairingCode}
            </p>
            <button
              type="button"
              onClick={handleCopy}
              title="Copy pairing code"
              className="p-1.5 rounded-md hover:bg-gray-200 transition-colors"
            >
              {copied ? (
                <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              ) : (
                <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                </svg>
              )}
            </button>
          </div>
          <p className="text-xs text-gray-600 text-center mb-3">
            {config.pairingInstruction(pairingCode, channelInfo?.username)}
          </p>
          <button
            onClick={handleCancelPairing}
            className="w-full px-3 py-1.5 text-xs font-medium text-gray-600 border border-gray-300 rounded-md hover:bg-gray-100 transition-colors"
          >
            Cancel Linking
          </button>
        </div>
      )}

      {/* Expired pairing code */}
      {!isPaired && pairingCode && !pairingActive && enabled && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3 text-center">
          <p className="text-sm text-yellow-700 mb-2">
            Code expired. Generate a new one.
          </p>
          <div className="flex gap-2 justify-center">
            <button
              onClick={handleGenerateCode}
              disabled={loading}
              className="px-4 py-1.5 text-xs font-medium text-blue-600 border border-blue-300 rounded-md hover:bg-blue-50 disabled:opacity-50"
            >
              {loading ? "Generating..." : "Generate New Code"}
            </button>
            <button
              onClick={handleCancelPairing}
              className="px-4 py-1.5 text-xs font-medium text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Setup guide */}
      {enabled && (
        <SetupGuide config={config} channelInfo={channelInfo} />
      )}
    </div>
  );
}

// -- Main page --

// -- Helper: read/write channel toggles from localStorage --

function getStoredToggles(): Record<string, boolean> {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem("blitz_channel_toggles");
    return raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

function setStoredToggles(toggles: Record<string, boolean>) {
  localStorage.setItem("blitz_channel_toggles", JSON.stringify(toggles));
}

export default function ChannelLinkingPage() {
  const [accounts, setAccounts] = useState<ChannelAccountResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [channelInfo, setChannelInfo] = useState<Record<string, ChannelInfoEntry>>({});
  const [toggles, setToggles] = useState<Record<string, boolean>>(() => {
    const stored = getStoredToggles();
    // Default all channels to disabled
    const defaults: Record<string, boolean> = {};
    for (const ch of CHANNELS) {
      defaults[ch.key] = stored[ch.key] ?? false;
    }
    return defaults;
  });

  const handleToggle = useCallback((channel: string, val: boolean) => {
    setToggles((prev) => {
      const next = { ...prev, [channel]: val };
      setStoredToggles(next);
      return next;
    });
  }, []);

  const loadAccounts = useCallback(async () => {
    try {
      const res = await fetch("/api/channels/accounts", { cache: "no-store" });
      if (res.ok) {
        const data = (await res.json()) as ChannelAccountResponse[];
        setAccounts(data);
        // Auto-enable toggles for channels that have linked accounts
        if (data.length > 0) {
          setToggles((prev) => {
            const next = { ...prev };
            let changed = false;
            for (const acct of data) {
              if (!next[acct.channel]) {
                next[acct.channel] = true;
                changed = true;
              }
            }
            if (changed) setStoredToggles(next);
            return changed ? next : prev;
          });
        }
      }
    } catch {
      // silently fail — empty accounts displayed
    } finally {
      setLoading(false);
    }
  }, []);

  const loadChannelInfo = useCallback(async () => {
    try {
      const res = await fetch("/api/channels/info", { cache: "no-store" });
      if (res.ok) {
        const data = (await res.json()) as Record<string, ChannelInfoEntry>;
        setChannelInfo(data);
      }
    } catch {
      // silently fail — channel info is optional
    }
  }, []);

  useEffect(() => {
    void loadAccounts();
    void loadChannelInfo();
  }, [loadAccounts, loadChannelInfo]);

  const handleLink = async (_channel: string) => {
    // Pairing code generation is handled in the ChannelCard component
    // This callback exists for future extensibility
  };

  const handleUnlink = async (accountId: string, _channelName: string) => {
    const res = await fetch(`/api/channels/accounts/${accountId}`, {
      method: "DELETE",
    });
    if (res.ok || res.status === 204) {
      setAccounts((prev) => prev.filter((a) => a.id !== accountId));
    }
  };

  const getAccountForChannel = (channelKey: string) =>
    accounts.find((a) => a.channel === channelKey);

  if (loading) {
    return <div className="p-8 text-gray-500">Loading...</div>;
  }

  return (
    <main className="max-w-2xl mx-auto p-8">
      <div className="mb-6">
        <Link
          href="/settings"
          className="text-sm text-blue-600 hover:underline"
        >
          &larr; Back to Settings
        </Link>
      </div>

      <h1 className="text-2xl font-semibold mb-2">Channel Linking</h1>
      <p className="text-sm text-gray-500 mb-6">
        Connect your messaging accounts to chat with Blitz from Telegram,
        WhatsApp, or Microsoft Teams.
      </p>

      <div className="space-y-4">
        {CHANNELS.map((config) => (
          <ChannelCard
            key={config.key}
            config={config}
            account={getAccountForChannel(config.key)}
            enabled={toggles[config.key] ?? false}
            channelInfo={channelInfo[config.key]}
            onToggle={handleToggle}
            onLink={handleLink}
            onUnlink={handleUnlink}
            onRefresh={loadAccounts}
          />
        ))}
      </div>
    </main>
  );
}
