# The 9 Option Backtesting Policies

All 9 policies govern **what to do after a CSP gets assigned and you now own the underlying**. The CSP entry rule is fixed across all of them; they only differ in the post-assignment behavior and whether risk stops are layered on.

## The 3 base post-assignment behaviors

1. **`liquidate`** - Sell the assigned shares at the next Monday close. Crystallize the loss, return to cash, restart CSPs immediately. No CC ever written.

2. **`hold_idle`** - Hold the assigned shares idle, waiting for spot to recover to your cost basis (breakeven), then sell. No CC written while waiting.

3. **Wheel** - While holding shares, sell a covered call each Monday. Three flavors of how aggressive the strike is:
   - **`strict_wheel`** - Only sell a CC at `strike >= assigned_strike`. If no OTM strike clears the cost basis, skip the week. Refuses to lock in a loss.
   - **`safe_wheel`** - Try strict first; if nothing qualifies, fall back to the **furthest-OTM** call that still meets the yield target (may sell below cost basis but at the safest available strike).
   - **`aggressive_wheel`** - Always sell the CC that hits the target yield, even if the strike is below your cost basis. Maximum premium income, accepts being called away at a loss.

## The `_stops` modifier

Each of the 4 holding policies (`hold_idle`, `strict_wheel`, `safe_wheel`, `aggressive_wheel`) has a `_no_stops` and a `_stops` variant. `_stops` adds two risk overlays:

- **8-week time stop** - if still holding after 8 weeks, force-exit
- **20% drawdown stop** - if unrealized loss hits -20%, force-exit

`liquidate` has no variants because it exits immediately by definition.

## The 9 policies, enumerated

| # | Policy | Holds shares? | Writes CCs? | Strike rule | Stops? |
|---|---|---|---|---|---|
| 1 | `liquidate` | no | no | n/a | n/a |
| 2 | `hold_idle_no_stops` | yes | no | n/a | no |
| 3 | `hold_idle_stops` | yes | no | n/a | yes |
| 4 | `strict_wheel_no_stops` | yes | yes | `strike >= cost basis` only | no |
| 5 | `strict_wheel_stops` | yes | yes | `strike >= cost basis` only | yes |
| 6 | `safe_wheel_no_stops` | yes | yes | strict, else furthest-OTM | no |
| 7 | `safe_wheel_stops` | yes | yes | strict, else furthest-OTM | yes |
| 8 | `aggressive_wheel_no_stops` | yes | yes | always hit target yield | no |
| 9 | `aggressive_wheel_stops` | yes | yes | always hit target yield | yes |

All 9 are run against the same 5 CSP yield targets (1%-5% per week), giving a 9 x 5 = 45-cell grid evaluated per IV tier (Low/Mid/High). `buy_and_hold_spy` in the CSV is the benchmark, not one of the 9.
