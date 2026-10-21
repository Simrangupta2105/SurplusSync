"""URL routes for predictions app."""

from django.urls import path
from predictions.views import DatasetInsightsView, PlanPredictionView

app_name = "predictions"

urlpatterns = [
    path("plan/", PlanPredictionView.as_view(), name="plan-prediction"),
    path("insights/", DatasetInsightsView.as_view(), name="dataset-insights"),
]
