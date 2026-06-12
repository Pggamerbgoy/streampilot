import joblib
import numpy as np
import os
import pandas as pd
import pytest


model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models', 'base_intelligence_rf.pkl')


def test_stream_pilot_ml_model_predicts_sample_titles():
    if not os.path.exists(model_path):
        pytest.skip("Local trained model is not committed. Run backend/train_model.py to generate it.")

    model = joblib.load(model_path)

    test_titles = [
        "this is a normal video about a gaming pc",
        "THIS IS A NORMAL VIDEO ABOUT A GAMING PC",
        "The Ultimate Gaming PC Build for 2026",
        "Don't buy a prebuilt PC until you watch this",
        "The Secret Truth About Why I Regret Buying The Ultimate $5000 Gaming PC Build In 2026 Before Watching This Insane Review",
    ]

    power_words = ["ultimate", "destroy", "banned", "secret", "truth", "insane", "best", "worst"]
    negative_hooks = ["don't", "stop", "regret", "never", "hate", "scam"]

    results = []

    for title in test_titles:
        t_len = len(title)
        c_ratio = sum(1 for c in title if c.isupper()) / t_len if t_len > 0 else 0
        has_power = 1 if any(w in title.lower() for w in power_words) else 0
        has_neg = 1 if any(w in title.lower() for w in negative_hooks) else 0
        thumb_contrast = 60
        face_prom = 50

        features = np.array([[t_len, c_ratio, has_power, has_neg, thumb_contrast, face_prom]])
        predicted_ctr = model.predict(features)[0]

        results.append({
            "Title": f'"{title}"',
            "Length": t_len,
            "Caps Ratio": f"{c_ratio:.0%}",
            "Power W.": "Yes" if has_power else "No",
            "Neg Hook": "Yes" if has_neg else "No",
            "Predicted CTR": f"{predicted_ctr:.2f}%"
        })

    df = pd.DataFrame(results)
    assert len(df) == len(test_titles)
    assert df["Predicted CTR"].str.endswith("%").all()
