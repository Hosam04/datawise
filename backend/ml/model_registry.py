"""Model registry and instance building for MLAnalyzer.

Contains allowed model lists, lazy model class loading, and model instance
configuration with appropriate hyperparameters.
"""
import logging
import warnings
from typing import Optional, List

import pandas as pd

logger = logging.getLogger("MLAnalyzer.model_registry")
warnings.filterwarnings("ignore")

# ─── Allowed Models Registry (EXPANDED) ───
ALLOWED_MODELS = {
    "classification": [
        "catboost", "xgboost", "lightgbm", "gradient_boosting", "adaboost",
        "random_forest", "extra_trees", "decision_tree",
        "logistic_regression", "svm", "knn", "naive_bayes",
    ],
    "regression": [
        "catboost_regressor", "xgboost_regressor", "lightgbm_regressor",
        "gradient_boosting_regressor",
        "random_forest_regressor", "extra_trees_regressor", "decision_tree_regressor",
        "linear_regression", "ridge", "lasso", "elasticnet",
        "svr", "knn_regressor",
    ],
    "text_classification": ["tfidf_logistic_regression"],
}

MAX_ROWS_FOR_TRAINING = 50_000
MIN_ROWS_FOR_ML = 100

# Models that handle categorical features natively
NATIVE_CATEGORICAL_MODELS = {"catboost", "catboost_regressor", "lightgbm", "lightgbm_regressor"}

# Models that need scaling
NEEDS_SCALING = {
    "svm", "svr", "knn", "knn_regressor",
    "logistic_regression", "linear_regression",
    "ridge", "lasso", "elasticnet",
}


def _get_model_class(model_name: str):
    """Lazy-load model classes to avoid heavy imports at startup."""

    # ─── CatBoost ───
    if model_name == "catboost":
        try:
            from catboost import CatBoostClassifier
            return CatBoostClassifier
        except ImportError:
            logger.warning("CatBoost not installed.")
            return None
    elif model_name == "catboost_regressor":
        try:
            from catboost import CatBoostRegressor
            return CatBoostRegressor
        except ImportError:
            logger.warning("CatBoost not installed.")
            return None

    # ─── XGBoost ───
    elif model_name == "xgboost":
        try:
            from xgboost import XGBClassifier
            return XGBClassifier
        except ImportError:
            logger.warning("XGBoost not installed.")
            return None
    elif model_name == "xgboost_regressor":
        try:
            from xgboost import XGBRegressor
            return XGBRegressor
        except ImportError:
            logger.warning("XGBoost not installed.")
            return None

    # ─── LightGBM ───
    elif model_name == "lightgbm":
        try:
            from lightgbm import LGBMClassifier
            return LGBMClassifier
        except ImportError:
            logger.warning("LightGBM not installed.")
            return None
    elif model_name == "lightgbm_regressor":
        try:
            from lightgbm import LGBMRegressor
            return LGBMRegressor
        except ImportError:
            logger.warning("LightGBM not installed.")
            return None

    # ─── Gradient Boosting ───
    elif model_name == "gradient_boosting":
        from sklearn.ensemble import GradientBoostingClassifier
        return GradientBoostingClassifier
    elif model_name == "gradient_boosting_regressor":
        from sklearn.ensemble import GradientBoostingRegressor
        return GradientBoostingRegressor

    # ─── AdaBoost ───
    elif model_name == "adaboost":
        from sklearn.ensemble import AdaBoostClassifier
        return AdaBoostClassifier

    # ─── Random Forest ───
    elif model_name == "random_forest":
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier
    elif model_name == "random_forest_regressor":
        from sklearn.ensemble import RandomForestRegressor
        return RandomForestRegressor

    # ─── Extra Trees ───
    elif model_name == "extra_trees":
        from sklearn.ensemble import ExtraTreesClassifier
        return ExtraTreesClassifier
    elif model_name == "extra_trees_regressor":
        from sklearn.ensemble import ExtraTreesRegressor
        return ExtraTreesRegressor

    # ─── Decision Tree ───
    elif model_name == "decision_tree":
        from sklearn.tree import DecisionTreeClassifier
        return DecisionTreeClassifier
    elif model_name == "decision_tree_regressor":
        from sklearn.tree import DecisionTreeRegressor
        return DecisionTreeRegressor

    # ─── Linear Models ───
    elif model_name == "logistic_regression":
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression
    elif model_name == "linear_regression":
        from sklearn.linear_model import LinearRegression
        return LinearRegression
    elif model_name == "ridge":
        from sklearn.linear_model import Ridge
        return Ridge
    elif model_name == "lasso":
        from sklearn.linear_model import Lasso
        return Lasso
    elif model_name == "elasticnet":
        from sklearn.linear_model import ElasticNet
        return ElasticNet

    # ─── SVM ───
    elif model_name == "svm":
        from sklearn.svm import SVC
        return SVC
    elif model_name == "svr":
        from sklearn.svm import SVR
        return SVR

    # ─── KNN ───
    elif model_name == "knn":
        from sklearn.neighbors import KNeighborsClassifier
        return KNeighborsClassifier
    elif model_name == "knn_regressor":
        from sklearn.neighbors import KNeighborsRegressor
        return KNeighborsRegressor

    # ─── Naive Bayes ───
    elif model_name == "naive_bayes":
        from sklearn.naive_bayes import GaussianNB
        return GaussianNB

    # ─── Text Classification ───
    elif model_name == "tfidf_logistic_regression":
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression

    return None


def _is_model_available(model_name: str) -> bool:
    return _get_model_class(model_name) is not None


def _build_model_instance(model_name: str, model_class, X_train: pd.DataFrame, categorical_cols: List[str]):
    """Build model instance with appropriate hyperparameters."""

    if model_name in ("catboost", "catboost_regressor"):
        cat_features = [i for i, c in enumerate(X_train.columns) if c in categorical_cols]
        return model_class(
            iterations=500, depth=6, learning_rate=0.1,
            verbose=False, random_seed=42,
            cat_features=cat_features if cat_features else None,
            allow_writing_files=False
        )

    elif model_name in ("xgboost", "xgboost_regressor"):
        return model_class(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            random_state=42, verbosity=0,
            enable_categorical=False,
        )

    elif model_name in ("lightgbm", "lightgbm_regressor"):
        return model_class(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            random_state=42, verbose=-1,
        )

    elif model_name in ("gradient_boosting", "gradient_boosting_regressor"):
        return model_class(
            n_estimators=200, max_depth=5, learning_rate=0.1,
            random_state=42,
        )

    elif model_name == "adaboost":
        return model_class(n_estimators=100, random_state=42)

    elif model_name in ("random_forest", "random_forest_regressor"):
        n_estimators = 100 if len(X_train) < 10000 else 50
        return model_class(n_estimators=n_estimators, random_state=42, n_jobs=-1)

    elif model_name in ("extra_trees", "extra_trees_regressor"):
        n_estimators = 100 if len(X_train) < 10000 else 50
        return model_class(n_estimators=n_estimators, random_state=42, n_jobs=-1)

    elif model_name in ("decision_tree", "decision_tree_regressor"):
        return model_class(max_depth=10, random_state=42)

    elif model_name == "logistic_regression":
        return model_class(max_iter=1000, random_state=42)

    elif model_name in ("linear_regression",):
        return model_class()

    elif model_name == "ridge":
        return model_class(alpha=1.0, random_state=42)

    elif model_name == "lasso":
        return model_class(alpha=1.0, random_state=42, max_iter=5000)

    elif model_name == "elasticnet":
        return model_class(alpha=1.0, l1_ratio=0.5, random_state=42, max_iter=5000)

    elif model_name == "svm":
        base = model_class(kernel="rbf", random_state=42)
        from sklearn.calibration import CalibratedClassifierCV
        return CalibratedClassifierCV(base, ensemble=False)

    elif model_name == "svr":
        return model_class(kernel="rbf")

    elif model_name in ("knn", "knn_regressor"):
        return model_class(n_neighbors=5, weights="distance")

    elif model_name == "naive_bayes":
        return model_class()

    elif model_name == "tfidf_logistic_regression":
        return model_class(max_iter=1000, random_state=42)

    else:
        return model_class()