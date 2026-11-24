"""
NFL playoff seeding with the official tiebreaking procedures.

Pure Python (no Streamlit / pandas), so it can be tested on its own.

Implemented, in order:

DIVISION tiebreakers
  Two clubs : head-to-head, division record, common games (min 4),
              conference record, strength of victory, strength of schedule,
              net points in conference games, net points in all games.
  3+ clubs  : head-to-head sweep, then the same steps as above.
              Whenever the group is reduced, the procedure restarts from
              step 1 (and uses the two-club rules once two clubs remain).

WILD CARD / SEEDING tiebreakers
  Two clubs : head-to-head, conference record, common games (min 4),
              strength of victory, strength of schedule,
              net points in conference games, net points in all games.
  3+ clubs  : head-to-head sweep, then the same steps as above.
  Clubs from the same division are first reduced to the single best club
  using the division tiebreakers, then that club competes in the wild card
  tiebreak.

Not implemented: the "combined ranking in points scored / points allowed"
steps (they need league-wide ranking data) and the coin toss. Those are
skipped; any tie that survives every implemented step is settled
alphabetically by team code so results stay deterministic.
"""

from collections import defaultdict


def _pct(wins, losses, ties):
    games = wins + losses + ties
    return (wins + 0.5 * ties) / games if games else 0.0


class SeedingContext:
    def __init__(self, results, teams):
        self.teams = teams
        # games[team] -> list of (opponent, points_for, points_against)
        self.games = defaultdict(list)

        for game in results:
            home, away = game.get("home"), game.get("away")
            if home not in teams or away not in teams:
                continue
            try:
                hs = int(game["home_score"])
                as_ = int(game["away_score"])
            except (KeyError, TypeError, ValueError):
                continue
            self.games[home].append((away, hs, as_))
            self.games[away].append((home, as_, hs))

    # ---------- basic helpers ----------

    def conf(self, code):
        return self.teams[code].get("conf")

    def div(self, code):
        return self.teams[code].get("div")

    def same_div(self, a, b):
        return self.conf(a) == self.conf(b) and self.div(a) == self.div(b)

    @staticmethod
    def _wlt(games):
        w = sum(1 for _, pf, pa in games if pf > pa)
        l = sum(1 for _, pf, pa in games if pf < pa)
        t = sum(1 for _, pf, pa in games if pf == pa)
        return w, l, t

    def pct(self, code, games=None):
        games = self.games[code] if games is None else games
        return _pct(*self._wlt(games))

    def overall_pct(self, code):
        return self.pct(code)

    # ---------- tiebreak metrics ----------

    def h2h_games(self, code, others):
        return [g for g in self.games[code] if g[0] in others]

    def division_pct(self, code):
        return self.pct(code, [g for g in self.games[code] if self.same_div(code, g[0])])

    def conference_pct(self, code):
        return self.pct(code, [g for g in self.games[code] if self.conf(g[0]) == self.conf(code)])

    def common_record(self, code, common):
        return [g for g in self.games[code] if g[0] in common]

    def strength_of_victory(self, code):
        beaten = [g[0] for g in self.games[code] if g[1] > g[2]]
        return self._combined_pct(beaten)

    def strength_of_schedule(self, code):
        return self._combined_pct([g[0] for g in self.games[code]])

    def _combined_pct(self, opponents):
        w = l = t = 0
        for opp in opponents:
            ow, ol, ot = self._wlt(self.games[opp])
            w, l, t = w + ow, l + ol, t + ot
        return _pct(w, l, t)

    def net_points(self, code, games=None):
        games = self.games[code] if games is None else games
        return sum(pf - pa for _, pf, pa in games)

    def net_points_conf(self, code):
        return self.net_points(
            code, [g for g in self.games[code] if self.conf(g[0]) == self.conf(code)]
        )

    # ---------- tiebreak steps ----------
    # Each step takes (group) and returns (survivors, label) or None if it
    # cannot separate the clubs. "survivors" is the best subset (or the
    # group minus eliminated clubs for the sweep rule).

    def _best_by(self, group, metric):
        values = {c: metric(c) for c in group}
        top = max(values.values())
        survivors = [c for c in group if abs(values[c] - top) < 1e-9]
        return survivors if len(survivors) < len(group) else None

    def step_head_to_head(self, group):
        if len(group) == 2:
            a, b = group
            ga, gb = self.h2h_games(a, {b}), self.h2h_games(b, {a})
            if not ga:
                return None
            survivors = self._best_by(group, lambda c: self.pct(c, self.h2h_games(c, set(group) - {c})))
            return (survivors, "Head-to-head") if survivors else None

        # 3+ clubs: sweep rule only
        swept_all, lost_all = [], []
        for c in group:
            others = set(group) - {c}
            games = self.h2h_games(c, others)
            if {g[0] for g in games} != others:
                continue  # hasn't played everyone -> rule can't apply to c
            w, l, _ = self._wlt(games)
            if l == 0 and w > 0 and all(g[1] > g[2] for g in games):
                swept_all.append(c)
            if w == 0 and all(g[1] < g[2] for g in games):
                lost_all.append(c)
        if len(swept_all) == 1:
            return (swept_all, "Head-to-head sweep")
        if lost_all and len(lost_all) < len(group):
            return ([c for c in group if c not in lost_all], "Head-to-head sweep")
        return None

    def step_division_record(self, group):
        s = self._best_by(group, self.division_pct)
        return (s, "Division record") if s else None

    def step_conference_record(self, group):
        s = self._best_by(group, self.conference_pct)
        return (s, "Conference record") if s else None

    def step_common_games(self, group):
        # common opponents must be common to ALL clubs in the group
        common = set.intersection(*[
            {g[0] for g in self.games[c] if g[0] not in group} for c in group
        ])
        if any(len(self.common_record(c, common)) < 4 for c in group):
            return None
        s = self._best_by(group, lambda c: self.pct(c, self.common_record(c, common)))
        return (s, "Common games") if s else None

    def step_sov(self, group):
        s = self._best_by(group, self.strength_of_victory)
        return (s, "Strength of victory") if s else None

    def step_sos(self, group):
        s = self._best_by(group, self.strength_of_schedule)
        return (s, "Strength of schedule") if s else None

    def step_net_conf(self, group):
        s = self._best_by(group, self.net_points_conf)
        return (s, "Net points (conference games)") if s else None

    def step_net_all(self, group):
        s = self._best_by(group, self.net_points)
        return (s, "Net points (all games)") if s else None

    # ---------- tie breaking ----------

    def _division_steps(self):
        return [
            self.step_head_to_head, self.step_division_record,
            self.step_common_games, self.step_conference_record,
            self.step_sov, self.step_sos,
            self.step_net_conf, self.step_net_all,
        ]

    def _wildcard_steps(self):
        return [
            self.step_head_to_head, self.step_conference_record,
            self.step_common_games, self.step_sov, self.step_sos,
            self.step_net_conf, self.step_net_all,
        ]

    def break_tie(self, group, kind):
        """Return (winner, reason). kind is 'division' or 'wildcard'."""
        group = sorted(group)
        reason = None
        steps = self._division_steps() if kind == "division" else self._wildcard_steps()

        while len(group) > 1:
            for step in steps:
                outcome = step(group)
                if outcome:
                    group, reason = sorted(outcome[0]), outcome[1]
                    break  # restart from step 1 with the reduced group
            else:
                group = group[:1]  # alphabetical fallback (coin toss stand-in)
                reason = "Coin toss (not modelled)"
        return group[0], reason

    def pick_wildcard(self, pool):
        """Best club in a pool that is already tied on overall record."""
        pool = sorted(pool)
        if len(pool) == 1:
            return pool[0], None

        # Reduce each division's members to its single best club first.
        reps, rep_reason = {}, {}
        by_div = defaultdict(list)
        for c in pool:
            by_div[(self.conf(c), self.div(c))].append(c)
        for members in by_div.values():
            if len(members) == 1:
                reps[members[0]] = members[0]
            else:
                best, why = self.break_tie(members, "division")
                for m in members:
                    reps[m] = best
                rep_reason[best] = why

        candidates = sorted(set(reps.values()))
        if len(candidates) == 1:
            return candidates[0], rep_reason.get(candidates[0])
        winner, why = self.break_tie(candidates, "wildcard")
        return winner, why

    # ---------- ranking ----------

    def _rank_pool(self, pool, picker):
        """Repeatedly pull the best club out of the pool. Returns [(code, reason)]."""
        pool, ordered = list(pool), []
        while pool:
            top = max(self.overall_pct(c) for c in pool)
            tied = [c for c in pool if abs(self.overall_pct(c) - top) < 1e-9]
            winner, why = picker(tied)
            ordered.append((winner, why if len(tied) > 1 else None))
            pool.remove(winner)
        return ordered

    def seed_conference(self, conference):
        conf_teams = [c for c in self.teams if self.conf(c) == conference]
        divisions = sorted({self.div(c) for c in conf_teams})

        # 1. Division winners
        winners = {}
        for d in divisions:
            members = [c for c in conf_teams if self.div(c) == d]
            top = max(self.overall_pct(c) for c in members)
            tied = [c for c in members if abs(self.overall_pct(c) - top) < 1e-9]
            winner, why = (tied[0], None) if len(tied) == 1 else self.break_tie(tied, "division")
            winners[d] = (winner, why)

        # 2. Seed the division winners 1-4 (different divisions: wildcard rules)
        winner_codes = [w for w, _ in winners.values()]
        division_seeds = self._rank_pool(
            winner_codes, lambda tied: (tied[0], None) if len(tied) == 1 else self.break_tie(tied, "wildcard")
        )

        # 3. Wild cards from everyone else
        rest = [c for c in conf_teams if c not in winner_codes]
        ranked_rest = self._rank_pool(rest, self.pick_wildcard)

        return division_seeds, ranked_rest
