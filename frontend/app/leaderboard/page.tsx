import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function LeaderboardPage() {
  let bots: { id: number; name: string; elo: number; version: number }[] = [];
  let users: { id: number; login: string; elo: number }[] = [];
  try {
    bots = await api.botLeaderboard();
  } catch {
    bots = [];
  }
  try {
    users = await api.userLeaderboard();
  } catch {
    users = [];
  }
  return (
    <div className="grid md:grid-cols-2 gap-8">
      <section>
        <h2 className="text-xl font-semibold mb-3">Bot ELO ladder</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-neutral-400">
            <tr>
              <th className="py-2">#</th>
              <th>bot</th>
              <th className="text-right">elo</th>
            </tr>
          </thead>
          <tbody>
            {bots.map((b, i) => (
              <tr key={b.id} className="border-t border-neutral-800">
                <td className="py-2">{i + 1}</td>
                <td>{b.name} v{b.version}</td>
                <td className="text-right">{b.elo.toFixed(0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section>
        <h2 className="text-xl font-semibold mb-3">Player ELO ladder</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-neutral-400">
            <tr>
              <th className="py-2">#</th>
              <th>player</th>
              <th className="text-right">elo</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u, i) => (
              <tr key={u.id} className="border-t border-neutral-800">
                <td className="py-2">{i + 1}</td>
                <td>{u.login}</td>
                <td className="text-right">{u.elo.toFixed(0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
