"""Exploratory, consumed-history full-grid diagnostic. No reserved data read."""
from pathlib import Path
from datetime import datetime, timezone
import json, time
import numpy as np
import pandas as pd
from validation import (shared_block_max_t_test,
                        moving_block_bootstrap_mean_ci,
                        family_plateau_support)

ROOT = Path(__file__).parent
OUT = ROOT / 'results'
PARAMS = ['tf', 'window', 'stop_atr', 'reward_r', 'max_hold', 'context', 'direction']


def serializable(obj):
    if isinstance(obj, (float, np.floating)) and not np.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {str(k): serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serializable(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    return obj


def main():
    assets = {}
    for a in ['NQ', 'ES']:
        p = OUT / a
        daily = np.load(p / 'daily_stressed.npz', allow_pickle=False)['daily']
        conf = json.loads((p / 'configs.json').read_text())
        manifest = json.loads((p / 'manifest.json').read_text())
        stats = pd.read_csv(p / 'all_config_metrics.csv')
        assets[a] = {'daily': daily, 'configs': conf, 'dates': manifest['sessions'],
                     'stats': stats, 'manifest': manifest}
    common = sorted(set(assets['NQ']['dates']) & set(assets['ES']['dates']))
    matrices = []
    all_configs = []
    for a in ['NQ', 'ES']:
        ad = assets[a]
        index = {d: i for i, d in enumerate(ad['dates'])}
        take = [index[d] for d in common]
        matrices.append(ad['daily'][:, take, 0].T)
        all_configs.extend(ad['configs'])
    combined = np.concatenate(matrices, axis=1)
    cases = [('combined_common_dates', combined, common, all_configs)]
    for a, ad in assets.items():
        cases.append((f'{a}_full_consumed_history', ad['daily'][:, :, 0].T,
                      ad['dates'], ad['configs']))
    results = {}
    for label, matrix, dates, configs in cases:
        start = time.perf_counter()
        print('Starting', label, matrix.shape, flush=True)
        r = shared_block_max_t_test(matrix, block_length=5, n_boot=1000,
                                   seed=20261025, batch_size=32)
        ids = [c['id'] for c in configs]
        ranking = pd.DataFrame({'id': ids, 'observed_t': r['observed_t'],
                                'adjusted_p': r['familywise_adjusted_p_values'],
                                'net': matrix.sum(axis=0),
                                'active_days': (matrix != 0).sum(axis=0)})
        ranking.to_csv(OUT / f'{label}_searchwide_statistics.csv', index=False)
        r['candidate_ids'] = ids
        r['first_session'] = dates[0]
        r['last_session'] = dates[-1]
        r['active_candidates'] = int((np.abs(matrix).sum(axis=0) > 0).sum())
        r['top_observed_t'] = ranking.sort_values('observed_t', ascending=False).head(20).to_dict('records')
        r['runtime_seconds'] = time.perf_counter() - start
        r['history_status'] = 'Previously inspected / researcher-consumed; not a fresh holdout.'
        results[label] = r
        print(label, 'global_p', r['global_p_value'], 'top', r['top_observed_t'][:5], flush=True)
        # Write incrementally so a long later diagnostic never loses completed work.
        document = {'created_utc': datetime.now(timezone.utc).isoformat(),
                    'purpose': 'Exploratory shared-block max-t diagnostic over ALL supplied stressed configurations.',
                    'reserved_data_read': False, 'bootstrap_samples': 1000,
                    'caveat': 'This is not a fresh holdout, a fully specified White Reality Check/Hansen SPA test, or a guarantee of familywise type-I error under nonstationary markets. Research iteration remains uncorrected.',
                    'cases': results}
        (OUT / 'searchwide_max_t.json').write_text(json.dumps(serializable(document), indent=2, allow_nan=False))
    robust = []
    for a, ad in assets.items():
        stats = ad['stats'].copy()
        n = len(ad['dates'])
        thirds = np.array_split(np.arange(n), 3)
        qs = pd.PeriodIndex(ad['dates'], freq='Q')
        unique_qs = qs.unique()
        stats['positive_thirds'] = [sum(ad['daily'][i, g, 0].sum() > 0 for g in thirds)
                                    for i in range(len(stats))]
        stats['positive_quarters'] = [sum(ad['daily'][i, qs == q, 0].sum() > 0 for q in unique_qs)
                                     for i in range(len(stats))]
        stats['quarters'] = len(unique_qs)
        plateau = family_plateau_support(stats, ad['configs'], param_keys=PARAMS,
                                         metric='stress_net')
        stats = stats.merge(plateau.drop(columns=['family', 'note']), on='id')
        stats['strict_pf_and_count'] = (stats.stress_pf >= 1.2) & (stats.trades >= 150)
        stats['strict_blocks_and_quarters'] = (stats.positive_thirds >= 2) & (stats.positive_quarters > stats.quarters / 2)
        stats['strict_neighbor_support'] = (stats.neighbors_with_scores >= 4) & (stats.positive_neighbor_fraction >= .6)
        stats.to_csv(OUT / a / 'full_consumed_history_stability.csv', index=False)
        keep = stats[stats.strict_pf_and_count & stats.strict_blocks_and_quarters & stats.strict_neighbor_support]
        candidates = []
        lookup = {c['id']: i for i, c in enumerate(ad['configs'])}
        for row in keep.to_dict('records'):
            ci = moving_block_bootstrap_mean_ci(ad['daily'][lookup[row['id']], :, 0], n_boot=2000)
            row.update(mean_daily_ci_low=ci['ci_low'], mean_daily_ci_high=ci['ci_high'],
                       strict_ci_positive=ci['ci_low'] > 0)
            candidates.append(row)
        robust.append({'asset': a, 'strict_pf_and_count_candidates': int(stats.strict_pf_and_count.sum()),
                       'all_pre_ci_gates_candidates': len(keep), 'candidates': candidates,
                       'top_net_not_gate_passes': stats.sort_values('stress_net', ascending=False).head(10).to_dict('records')})
    (OUT / 'strict_broad_history_screen.json').write_text(json.dumps(serializable({
        'reserved_data_read': False,
        'gates': 'Stressed PF>=1.20; >=150 trades; >=2/3 positive chronological thirds; strictly more than half quarters positive; >=4 neighbors with scores; >=60% positive neighbors; positive 95% block-bootstrap mean lower bound.',
        'warning': 'A proposed strict static screen on already consumed research data; do not loosen gates in response to its result and call that confirmation.',
        'assets': robust}), indent=2, allow_nan=False))
    print('Strict PF/count survivors:', [(x['asset'], x['strict_pf_and_count_candidates']) for x in robust], flush=True)


if __name__ == '__main__':
    main()
