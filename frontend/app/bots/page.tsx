"use client";

import { useEffect, useState } from "react";
import { api, BotOut } from "@/lib/api";

export default function BotsPage() {
  const [token, setToken] = useState("");
  const [bots, setBots] = useState<BotOut[]>([]);
  const [name, setName] = useState("my-bot");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  async function refresh() {
    if (!token) return;
    try {
      const list = await api.myBots(token);
      setBots(list);
      setStatus(null);
    } catch (e) {
      setStatus(String(e));
    }
  }

  useEffect(() => {
    if (token) void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !file) {
      setStatus("token + zip artifact required");
      return;
    }
    try {
      const bot = await api.uploadBot(token, name, file, description || undefined);
      setStatus(`uploaded ${bot.name} v${bot.version}`);
      void refresh();
    } catch (e) {
      setStatus(String(e));
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Your bots</h1>
      <label className="flex flex-col text-sm max-w-md">
        <span className="text-neutral-400">jwt</span>
        <input
          className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="paste your JWT"
        />
      </label>

      <form
        onSubmit={upload}
        className="space-y-3 border border-neutral-800 rounded p-4 max-w-md"
        data-testid="upload-form"
      >
        <h2 className="font-semibold">Upload a new bot version</h2>
        <label className="flex flex-col text-sm">
          <span className="text-neutral-400">name</span>
          <input
            className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-col text-sm">
          <span className="text-neutral-400">description (optional)</span>
          <input
            className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <label className="flex flex-col text-sm">
          <span className="text-neutral-400">artifact (.zip with bot.py at root)</span>
          <input
            type="file"
            accept=".zip"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <button className="bg-blue-600 px-3 py-1 rounded" type="submit">
          upload
        </button>
        {status && <p className="text-sm text-amber-400">{status}</p>}
      </form>

      <section>
        <h2 className="font-semibold mb-2">My bots</h2>
        {bots.length === 0 ? (
          <p className="text-sm text-neutral-500">
            None yet (or paste a token above to load).
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-neutral-400">
              <tr>
                <th className="py-1">name</th>
                <th>v</th>
                <th>status</th>
                <th className="text-right">elo</th>
              </tr>
            </thead>
            <tbody>
              {bots.map((b) => (
                <tr key={b.id} className="border-t border-neutral-800">
                  <td className="py-1">{b.name}</td>
                  <td>v{b.version}</td>
                  <td>{b.status}</td>
                  <td className="text-right">{b.elo.toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
