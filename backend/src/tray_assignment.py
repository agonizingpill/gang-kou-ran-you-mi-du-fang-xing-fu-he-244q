"""Whole-tray one-to-one attribution solver.

Pure Python, no third-party deps: trays are small (<=8 bottles, <=8 candidate
tanks), so an exact DP over tank bitmasks replaces a greedy per-bottle pick.
A bottle is assigned only through an eligible edge (score >= grade threshold);
unassignable bottles stay unattributed instead of being force-matched.
"""

def solve(scores,eligible,forbidden=None):
    """Maximize (assigned_count,total_score) over one-to-one bottle->tank maps.

    scores[i][j]: log-likelihood of bottle i under candidate tank j's grade model.
    eligible[i][j]: hard gate; ineligible edges are never taken.
    forbidden: optional set of (i,j) edges additionally banned (k-best re-solve).
    Returns {'assign':{i:j},'count':int,'total':float}; deterministic on ties.
    """
    n=len(scores);m=len(scores[0])if n else 0;forbidden=forbidden or set()
    # dp[mask]=(count,total,path) after processing bottles 0..i-1; path[i]=j or -1
    dp={0:(0,0.0,())}
    for i in range(n):
        nxt={}
        for mask,(cnt,tot,path) in dp.items():
            skip=(cnt,tot,path+(-1,))
            cur=nxt.get(mask)
            if cur is None or(skip[0],skip[1])>(cur[0],cur[1]):nxt[mask]=skip
            for j in range(m):
                if mask>>j&1 or not eligible[i][j]or(i,j)in forbidden:continue
                key=mask|1<<j;cand=(cnt+1,tot+scores[i][j],path+(j,))
                cur=nxt.get(key)
                if cur is None or(cand[0],cand[1])>(cur[0],cur[1]):nxt[key]=cand
        dp=nxt
    cnt,tot,path=max(dp.values(),key=lambda v:(v[0],v[1]))
    return{'assign':{i:j for i,j in enumerate(path)if j>=0},'count':cnt,'total':tot}

def best_and_second(scores,eligible):
    """Best scheme plus the best distinct alternative (for near-tie review).

    Any scheme different from the optimum lacks at least one of the optimum's
    edges (assignment count is lexicographically dominant, so a same-count
    alternative must drop an optimal edge), thus forbidding each optimal edge
    in turn and re-solving finds the runner-up.
    """
    best=solve(scores,eligible);second=None
    for edge in best['assign'].items():
        alt=solve(scores,eligible,{edge})
        if second is None or(alt['count'],alt['total'])>(second['count'],second['total']):second=alt
    return best,second
