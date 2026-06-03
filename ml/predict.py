import argparse
import sys
import json
import joblib
import pandas as pd
from pathlib import Path
SCRIPT_DIR = Path(__file__).resolve().parent
MODELS_DIR = SCRIPT_DIR / "models"
def main():
    parser = argparse.ArgumentParser(description="Predictive Analytics Inference for IPL")
    parser.add_argument('--task', type=str, required=True, choices=['match_outcome', 'score_prediction', 'player_performance'])
    parser.add_argument('--team1', type=str)
    parser.add_argument('--team2', type=str)
    parser.add_argument('--venue', type=str)
    parser.add_argument('--toss_winner', type=str)
    parser.add_argument('--toss_decision', type=str)
    parser.add_argument('--innings', type=int)
    parser.add_argument('--current_score', type=float)
    parser.add_argument('--wickets', type=float)
    parser.add_argument('--overs_remaining', type=float)
    parser.add_argument('--batter', type=str)
    args = parser.parse_args()
    try:
        if args.task == 'match_outcome':
            model = joblib.load(MODELS_DIR / 'match_outcome_model.pkl')
            input_df = pd.DataFrame([{
                'team1': args.team1,
                'team2': args.team2,
                'venue': args.venue,
                'toss_winner': args.toss_winner,
                'toss_decision': args.toss_decision
            }])
            raw_prediction = model.predict(input_df)[0]
            probabilities = model.predict_proba(input_df)[0]
            classes = list(model.classes_)
            
            prob_t1 = float(probabilities[classes.index(args.team1)]) * 100.0 if args.team1 in classes else 0.0
            prob_t2 = float(probabilities[classes.index(args.team2)]) * 100.0 if args.team2 in classes else 0.0
            
            # Re-normalize only against the two playing teams
            total_prob = prob_t1 + prob_t2
            if total_prob > 0:
                prob_t1 = round((prob_t1 / total_prob) * 100.0, 1)
                prob_t2 = round((prob_t2 / total_prob) * 100.0, 1)
            else:
                prob_t1 = 50.0
                prob_t2 = 50.0

            # FORCE output prediction to be restricted only between team1 and team2
            if prob_t1 >= prob_t2:
                final_prediction = args.team1
                win_prob = prob_t1
            else:
                final_prediction = args.team2
                win_prob = prob_t2

            print(json.dumps({
                "success": True, 
                "task": args.task, 
                "prediction": str(final_prediction),
                "probability": win_prob,
                "team1_prob": prob_t1,
                "team2_prob": prob_t2,
                "message": f"{args.team1} ({prob_t1}%) vs {args.team2} ({prob_t2}%)"
            }))
        elif args.task == 'score_prediction':
            model = joblib.load(MODELS_DIR / 'score_prediction_model.pkl')
            input_df = pd.DataFrame([{
                'team1': args.team1,
                'team2': args.team2,
                'venue': args.venue,
                'innings': args.innings,
                'current_score': args.current_score,
                'wickets': args.wickets,
                'overs_remaining': args.overs_remaining
            }])
            prediction = model.predict(input_df)[0]
            print(json.dumps({
                "success": True, 
                "task": args.task, 
                "prediction": int(prediction),
                "message": f"Projected Score: {int(prediction)}"
            }))
        elif args.task == 'player_performance':
            model = joblib.load(MODELS_DIR / 'player_performance_model.pkl')
            input_df = pd.DataFrame([{
                'batter': args.batter,
                'team2': args.team2,
                'venue': args.venue
            }])
            prediction = model.predict(input_df)[0]
            print(json.dumps({
                "success": True, 
                "task": args.task, 
                "prediction": int(prediction),
                "message": f"Expected Runs for {args.batter}: {int(prediction)}"
            }))
    except FileNotFoundError:
        print(json.dumps({"success": False, "error": "Model file not found. Ensure models are trained first."}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
if __name__ == '__main__':
    main()
