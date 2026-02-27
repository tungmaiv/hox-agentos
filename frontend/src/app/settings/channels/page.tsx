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

// -- Channel configuration --

interface ChannelConfig {
  key: string;
  name: string;
  icon: string;
  pairingInstruction: (code: string) => string;
}

const CHANNELS: ChannelConfig[] = [
  {
    key: "telegram",
    name: "Telegram",
    icon: "T",
    pairingInstruction: (code: string) =>
      `Send /pair ${code} to @BlitzBot on Telegram`,
  },
  {
    key: "whatsapp",
    name: "WhatsApp",
    icon: "W",
    pairingInstruction: (code: string) =>
      `Send /pair ${code} to the Blitz number on WhatsApp`,
  },
  {
    key: "ms_teams",
    name: "Teams",
    icon: "M",
    pairingInstruction: (code: string) =>
      `Send /pair ${code} in a DM to Blitz Bot in Teams`,
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

// -- Channel Card component --

function ChannelCard({
  config,
  account,
  onLink,
  onUnlink,
}: {
  config: ChannelConfig;
  account: ChannelAccountResponse | undefined;
  onLink: (channel: string) => Promise<void>;
  onUnlink: (accountId: string, channelName: string) => Promise<void>;
}) {
  const [pairingCode, setPairingCode] = useState<string | null>(null);
  const [pairingActive, setPairingActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [confirmUnlink, setConfirmUnlink] = useState(false);

  const { remaining, display } = useCountdown(600, pairingActive);

  // When countdown reaches 0, expire the code
  useEffect(() => {
    if (pairingActive && remaining === 0) {
      setPairingActive(false);
      setPairingCode(null);
    }
  }, [pairingActive, remaining]);

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

  const isPaired = !!account;
  const displayName = account?.display_name || account?.external_user_id || "";

  return (
    <div className="border border-gray-200 rounded-lg p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center text-blue-700 font-bold text-lg">
            {config.icon}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-900">
              {config.name}
            </h3>
            {isPaired && (
              <p className="text-xs text-green-600 mt-0.5">
                Linked as {displayName}
              </p>
            )}
          </div>
        </div>

        {isPaired && !confirmUnlink && (
          <button
            onClick={() => setConfirmUnlink(true)}
            className="px-3 py-1.5 text-xs font-medium text-red-600 border border-red-200 rounded-md hover:bg-red-50 transition-colors"
          >
            Unlink
          </button>
        )}
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
      {!isPaired && !pairingCode && (
        <button
          onClick={handleGenerateCode}
          disabled={loading}
          className="w-full px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {loading ? "Generating..." : `Link ${config.name}`}
        </button>
      )}

      {/* Active pairing code with countdown */}
      {!isPaired && pairingCode && pairingActive && (
        <div className="bg-gray-50 border border-gray-200 rounded-md p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-gray-500">
              Pairing Code
            </span>
            <span className="text-xs text-gray-500">
              Code expires in {display}
            </span>
          </div>
          <p className="text-2xl font-mono font-bold text-center tracking-widest text-gray-900 mb-2">
            {pairingCode}
          </p>
          <p className="text-xs text-gray-600 text-center">
            {config.pairingInstruction(pairingCode)}
          </p>
        </div>
      )}

      {/* Expired pairing code */}
      {!isPaired && pairingCode && !pairingActive && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3 text-center">
          <p className="text-sm text-yellow-700 mb-2">
            Code expired. Generate a new one.
          </p>
          <button
            onClick={handleGenerateCode}
            disabled={loading}
            className="px-4 py-1.5 text-xs font-medium text-blue-600 border border-blue-300 rounded-md hover:bg-blue-50 disabled:opacity-50"
          >
            {loading ? "Generating..." : "Generate New Code"}
          </button>
        </div>
      )}
    </div>
  );
}

// -- Main page --

export default function ChannelLinkingPage() {
  const [accounts, setAccounts] = useState<ChannelAccountResponse[]>([]);
  const [loading, setLoading] = useState(true);

  const loadAccounts = useCallback(async () => {
    try {
      const res = await fetch("/api/channels/accounts", { cache: "no-store" });
      if (res.ok) {
        const data = (await res.json()) as ChannelAccountResponse[];
        setAccounts(data);
      }
    } catch {
      // silently fail — empty accounts displayed
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts]);

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
            onLink={handleLink}
            onUnlink={handleUnlink}
          />
        ))}
      </div>
    </main>
  );
}
