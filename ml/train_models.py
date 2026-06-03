"""
Master ML Pipeline Orchestrator.
Replaces the legacy simplified script.
Executes the entire advanced feature engineering -> lookups -> training pipeline in order.

Usage:
    python -m ml.train_models
"""
import time
import sys
from pathlib import Path

# Add project root to sys.path just in case it's run directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import main functions from the pipeline modules
from ml.features.build_features import main as build_features_main
from ml.build_lookups import main as build_lookups_main
from ml.train.train_match_outcome import main as train_match_outcome_main
from ml.train.train_score_predictor import main as train_score_predictor_main
from ml.train.train_player_perf import main as train_player_perf_main

def main():
    print("=" * 70)
    print("    STARTING FULL END-TO-END IPL MACHINE LEARNING PIPELINE    ")
    print("=" * 70)
    t0 = time.time()
    
    try:
        print("\n--- STEP 1/5: Building Feature Datasets ---")
        build_features_main()
        
        print("\n--- STEP 2/5: Pre-computing Inference Lookups ---")
        build_lookups_main()
        
        print("\n--- STEP 3/5: Training Match Outcome Model ---")
        train_match_outcome_main()
        
        print("\n--- STEP 4/5: Training Score Predictor ---")
        train_score_predictor_main()
        
        print("\n--- STEP 5/5: Training Player Performance Models ---")
        train_player_perf_main()
        
    except Exception as e:
        print("\n" + "!" * 70)
        print(f"PIPELINE FAILED: {str(e)}")
        print("!" * 70)
        sys.exit(1)
        
    print("\n" + "=" * 70)
    print(f"PIPELINE SUCCESSFULLY COMPLETED IN {time.time() - t0:.1f} SECONDS!")
    print("FastAPI is ready to serve the new models.")
    print("=" * 70)

if __name__ == '__main__':
    main()
