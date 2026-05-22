import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
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
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold">chesslab</h1>
        <p className="text-neutral-400 mt-2 text-sm">
          Build chess bots in Python (alpha-beta, actor-critic RL, anything you
          want), upload them, compete online, climb the ELO ladder.
        </p>
      </header>

      <section data-testid="bot-leaderboard">
        <h2 className="text-xl font-semibold mb-3">Top bots</h2>
        {bots.length === 0 ? (
          <p className="text-neutral-500 text-sm">
            No bots yet — upload one to get started.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-neutral-400">
              <tr>
                <th className="py-2">#</th>
                <th>name</th>
                <th>version</th>
                <th className="text-right">elo</th>
              </tr>
            </thead>
            <tbody>
              {bots.map((b, i) => (
                <tr key={b.id} className="border-t border-neutral-800">
                  <td className="py-2">{i + 1}</td>
                  <td>{b.name}</td>
                  <td>v{b.version}</td>
                  <td className="text-right">{b.elo.toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section data-testid="user-leaderboard">
        <h2 className="text-xl font-semibold mb-3">Top players</h2>
        {users.length === 0 ? (
          <p className="text-neutral-500 text-sm">
            No registered players yet — sign in with GitHub to join.
          </p>
        ) : (
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
        )}
      </section>
    </div>
  );
}
