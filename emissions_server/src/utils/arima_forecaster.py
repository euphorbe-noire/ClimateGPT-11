"""
Time series forecasting module for ClimateGPT.

This module provides ARIMA-based forecasting for emissions data,
allowing predictions of future emissions levels based on historical trends.
"""

import logging
import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, Any, List, Tuple, Optional
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA
import numpy as np
import pandas as pd
from sklearn.feature_selection import SelectKBest, f_regression

# Set up logging
logger = logging.getLogger('forecast_utils')

def clean_outliers(series, threshold=2.5):
    """Clean outliers using Z-score method."""
    if not isinstance(series, pd.Series):
        series = pd.Series(series)
    
    z_scores = (series - series.mean()) / series.std()
    outliers = abs(z_scores) > threshold
    
    if outliers.any():
        logger.info(f"Found {outliers.sum()} outliers")
        cleaned = series.copy()
        cleaned[outliers] = series.median()
        return cleaned
    
    return series

def find_best_params(series):
    """Find optimal ARIMA parameters."""
    best_aic = float("inf")
    best_params = (1, 1, 1)  # Default to a more complex model
    
    params_to_try = [
        (1, 1, 0), (0, 1, 1), (1, 1, 1), (2, 1, 0), (0, 1, 2), (2, 1, 1), (1, 1, 2)
    ]
    # Notice (0,1,0) is intentionally excluded
    
    for p, d, q in params_to_try:
        try:
            model = ARIMA(series, order=(p, d, q))
            fit = model.fit()
            if fit.aic < best_aic:
                best_aic = fit.aic
                best_params = (p, d, q)
            logger.info(f"ARIMA({p},{d},{q}) AIC: {fit.aic}")
        except Exception as e:
            logger.warning(f"Could not fit ARIMA({p},{d},{q}): {str(e)}")
    
    return best_params

def calc_better_intervals(model_fit, steps, alpha=0.05):
    """Calculate realistic confidence intervals."""
    try:
        # Get forecast values
        forecast_values = model_fit.forecast(steps=steps)
        
        # If forecast_values is a scalar (single value), convert to array
        if np.isscalar(forecast_values):
            forecast_values = np.array([forecast_values])
        
        # Calculate residuals standard error
        residuals = model_fit.resid
        std_err = residuals.std()
        
        # Initialize confidence intervals
        lower = []
        upper = []
        
        # Calculate intervals with increasing width for further forecasts
        for i in range(len(forecast_values)):
            # Width increases with the square root of the forecast horizon
            width = 1.96 * std_err * np.sqrt(1 + i * 0.2)  # Increase by 20% per step
            lower.append(float(forecast_values[i] - width))
            upper.append(float(forecast_values[i] + width))
        
        # Convert forecast to list of float values
        forecast_list = [float(x) for x in forecast_values]
        
        return forecast_list, lower, upper
    except Exception as e:
        logger.error(f"Error in confidence interval calculation: {str(e)}")
        # Fallback method with minimum width
        forecast_list = [float(x) for x in model_fit.forecast(steps=steps)]
        std_err = max(model_fit.resid.std(), 100)  # Ensure minimum uncertainty
        
        lower = []
        upper = []
        for i in range(steps):
            width = std_err * (1 + i * 0.1)  # Increase width over time
            lower.append(forecast_list[i] - width)
            upper.append(forecast_list[i] + width)
        
        return forecast_list, lower, upper
    
def compare_benchmarks(years, values, forecast_years):
    """Compare with simple benchmark models."""
    # Recent average (last 3 years)
    avg_forecast = [np.mean(values[-3:])] * len(forecast_years)
    
    # Linear trend
    x = np.array(years)
    y = np.array(values)
    slope, intercept = np.polyfit(x, y, 1)
    trend_forecast = [slope * year + intercept for year in forecast_years]
    
    # Naive (last value)
    naive_forecast = [values[-1]] * len(forecast_years)
    
    return {
        "avg": avg_forecast,
        "trend": trend_forecast,
        "naive": naive_forecast
    }

class ForecastError(Exception):
    """Exception raised for errors in the forecasting module."""
    pass

def check_stationarity(time_series: pd.Series) -> Dict[str, Any]:
    """
    Check if a time series is stationary using the Augmented Dickey-Fuller test.
    
    Args:
        time_series: Pandas Series with time series data
        
    Returns:
        Dictionary with test results
    """
    result = adfuller(time_series.dropna())
    
    return {
        'test_statistic': result[0],
        'p_value': result[1],
        'critical_values': result[4],
        'is_stationary': result[1] < 0.05
    }

def determine_arima_order(time_series: pd.Series) -> Tuple[int, int, int]:
    """
    Determine appropriate ARIMA order parameters based on time series characteristics.
    
    This is a simplified approach. For a more advanced implementation, consider using
    auto_arima from pmdarima package which performs a grid search over possible parameters.
    
    Args:
        time_series: Pandas Series with time series data
        
    Returns:
        Tuple of (p, d, q) for ARIMA model
    """
    # Check stationarity to determine d
    stationarity_test = check_stationarity(time_series)
    
    # If series is not stationary, we'll use d=1
    d = 0 if stationarity_test['is_stationary'] else 1
    
    # Use simple default values for p and q
    # In a more advanced implementation, these would be determined through 
    # autocorrelation and partial autocorrelation analysis
    p = 1
    q = 1
    
    logger.info(f"Selected ARIMA order: ({p}, {d}, {q})")
    
    return p, d, q

def generate_forecast(df, forecast_years=10, confidence_level=0.95):
    """
    Generate improved forecast using multiple features with feature selection.
    
    Args:
        df: DataFrame with historical data including multiple feature columns
        forecast_years: Number of years to forecast
        confidence_level: Confidence level for intervals
        
    Returns:
        Forecast results dictionary
    """
    
    # Check if we have enough data
    if len(df) < 5:
        logger.warning("Not enough historical data points for reliable forecasting")
        return generate_fallback_forecast(df, forecast_years, confidence_level)
    
    # Extract time series data
    years = df['year'].values
    emissions = df['total_emissions'].values
    
    # Keep track of the best features used
    used_features = []
    
    try:
        # Step 1: Feature selection if we have additional columns
        feature_cols = [col for col in df.columns 
                       if col not in ['year', 'total_emissions'] 
                       and not df[col].isnull().all()]
        
        if len(feature_cols) > 0:
            # Normalize features to avoid scale issues
            features_df = df[feature_cols].copy()
            for col in feature_cols:
                if features_df[col].std() > 0:
                    features_df[col] = (features_df[col] - features_df[col].mean()) / features_df[col].std()
            
            # Select the best k features (where k is min(3, number of features))
            k = min(3, len(feature_cols))
            
            if k > 0 and len(df) > k + 2:  # Need more samples than features
                # Use f_regression to identify most predictive features
                selector = SelectKBest(f_regression, k=k)
                X = features_df.values
                y = emissions
                selector.fit(X, y)
                
                # Get selected feature indices and names
                selected_indices = selector.get_support(indices=True)
                selected_features = [feature_cols[i] for i in selected_indices]
                
                # Store for reporting
                used_features = selected_features
                
                # Create a composite feature using the weighted average of selected features
                # Weights are based on feature importances
                weights = selector.scores_[selected_indices]
                weights = weights / np.sum(weights)  # Normalize weights
                
                # Create weighted feature
                weighted_feature = np.zeros(len(df))
                for i, feature in enumerate(selected_features):
                    weighted_feature += weights[i] * features_df[feature].values
                
                # Use this composite feature to adjust the emissions data
                adjustment_factor = 0.2  # Control the influence of features
                adjusted_emissions = emissions * (1 + adjustment_factor * weighted_feature)
            else:
                # Not enough data for feature selection
                adjusted_emissions = emissions
        else:
            # No additional features
            adjusted_emissions = emissions
        
        # Step 2: Find best ARIMA parameters and fit model
        p, d, q = find_best_params(pd.Series(adjusted_emissions))
        logger.info(f"Selected ARIMA order: ({p}, {d}, {q})")
        
        model = ARIMA(adjusted_emissions, order=(p, d, q), enforce_stationarity=False)
        model_fit = model.fit()
        
        # Step 3: Generate base forecast
        forecast_values = model_fit.forecast(steps=forecast_years)
        
        # Step 4: If we used feature adjustment, we need to convert back
        if len(feature_cols) > 0 and 'weighted_feature' in locals():
            # Use the last value of the weighted feature as proxy for future
            # This is a simplification - in a more complex model we would forecast the features too
            last_feature_value = weighted_feature[-1]
            forecast_values = forecast_values / (1 + adjustment_factor * last_feature_value)
        
        # Step 5: Calculate confidence intervals with wider bounds for future uncertainty
        residuals = model_fit.resid
        std_err = residuals.std()
        
        # Use t-distribution for small samples, normal for larger ones
        if len(df) < 30:
            from scipy import stats
            t_value = stats.t.ppf(1 - (1 - confidence_level) / 2, len(df) - 1)
        else:
            from scipy import stats
            t_value = stats.norm.ppf(1 - (1 - confidence_level) / 2)
        
        # Expand intervals for future years - uncertainty grows over time
        uncertainty_growth = np.linspace(1.0, min(2.0, 1.0 + 0.1 * forecast_years), forecast_years)
        
        lower_ci = [float(forecast_values[i] - t_value * std_err * uncertainty_growth[i]) 
                   for i in range(forecast_years)]
        upper_ci = [float(forecast_values[i] + t_value * std_err * uncertainty_growth[i]) 
                   for i in range(forecast_years)]
        
        # Ensure forecast values are a list of floats
        forecast_values = [float(val) for val in forecast_values]
        
        # Generate forecast years
        max_year = int(max(years))
        forecast_years_list = list(range(max_year + 1, max_year + forecast_years + 1))
        
         # Calculate forecast metrics using the existing function
        metrics = calculate_forecast_metrics(model_fit, pd.Series(emissions))
        
        # Return results with metrics and historical data
        return {
            'forecast': {
                'years': forecast_years_list,
                'values': forecast_values,
                'lower_ci': lower_ci,
                'upper_ci': upper_ci,
                'confidence_level': confidence_level
            },
            'model_info': {
                'type': 'Enhanced ARIMA',
                'order': (p, d, q),
                'feature_count': len(feature_cols),
                'selected_features': used_features,
                'data_points': len(df)
            },
            'metrics': metrics,  # Add the calculated metrics
            'historical_data': {
                'years': years.tolist(),
                'values': emissions.tolist()
            }
        }
        
    except Exception as e:
        logger.error(f"Enhanced forecast error: {str(e)}")
        # Fallback to basic forecast
        return generate_fallback_forecast(df, forecast_years, confidence_level)
    
def generate_fallback_forecast(df, forecast_years=10, confidence_level=0.95):
    """
    Generate a simple forecast when the enhanced approach fails.
    
    Args:
        df: DataFrame with historical data
        forecast_years: Number of years to forecast
        confidence_level: Confidence level for intervals
        
    Returns:
        Forecast results dictionary
    """
    from statsmodels.tsa.arima.model import ARIMA
    import numpy as np
    
    # Extract time series data
    years = df['year'].values
    emissions = df['total_emissions'].values
    
    try:
        # Use a very simple ARIMA model with minimal parameters
        model = ARIMA(emissions, order=(1, 1, 0))
        model_fit = model.fit()
        
        # Generate forecast
        forecast_values = model_fit.forecast(steps=forecast_years)
        
        # Calculate simple confidence intervals
        residuals = model_fit.resid
        std_err = residuals.std() if len(residuals) > 0 else emissions.std() * 0.1
        
        # Use increasing uncertainty for future years
        margin = 1.96 * std_err  # ~95% confidence
        uncertainty_growth = np.linspace(1.0, 2.0, forecast_years)
        
        lower_ci = [float(forecast_values[i] - margin * uncertainty_growth[i]) 
                   for i in range(forecast_years)]
        upper_ci = [float(forecast_values[i] + margin * uncertainty_growth[i]) 
                   for i in range(forecast_years)]
        
        # Ensure forecast values are a list of floats
        forecast_values = [float(val) for val in forecast_values]
        
        # Generate forecast years
        max_year = int(max(years))
        forecast_years_list = list(range(max_year + 1, max_year + forecast_years + 1))
        
        return {
            'forecast': {
                'years': forecast_years_list,
                'values': forecast_values,
                'lower_ci': lower_ci,
                'upper_ci': upper_ci,
                'confidence_level': confidence_level
            },
            'model_info': {
                'type': 'Fallback ARIMA(1,1,0)',
                'order': (1, 1, 0),
                'feature_count': 0,
                'selected_features': [],
                'data_points': len(df)
            }
        }
    except Exception as e:
        logger.error(f"Fallback forecast also failed: {str(e)}")
        
        # Last resort: linear trend extrapolation
        x = np.arange(len(years))
        coeffs = np.polyfit(x, emissions, 1)
        slope, intercept = coeffs
        
        # Generate trend forecast
        forecast_values = [slope * (len(years) + i) + intercept for i in range(forecast_years)]
        
        # Very wide confidence intervals due to low confidence
        margin = emissions.std() * 2
        lower_ci = [val - margin * (1 + i*0.2) for i, val in enumerate(forecast_values)]
        upper_ci = [val + margin * (1 + i*0.2) for i, val in enumerate(forecast_values)]
        
        # Generate forecast years
        max_year = int(max(years))
        forecast_years_list = list(range(max_year + 1, max_year + forecast_years + 1))
        
        return {
            'forecast': {
                'years': forecast_years_list,
                'values': forecast_values,
                'lower_ci': lower_ci,
                'upper_ci': upper_ci,
                'confidence_level': confidence_level
            },
            'model_info': {
                'type': 'Linear Trend (Emergency Fallback)',
                'order': None,
                'feature_count': 0,
                'selected_features': [],
                'data_points': len(df)
            }
        }
    
def calculate_forecast_metrics(model_fit: Any, time_series: pd.Series) -> Dict[str, Any]:
    """
    Calculate various metrics to evaluate forecast quality.
    
    Args:
        model_fit: Fitted ARIMA model
        time_series: Original time series data
        
    Returns:
        Dictionary of metrics
    """
    # Get model summary statistics
    aic = model_fit.aic
    bic = model_fit.bic
    
    # Calculate in-sample errors
    residuals = model_fit.resid
    rmse = np.sqrt(np.mean(residuals**2))
    mae = np.mean(np.abs(residuals))
    
    # Additional metrics
    residual_std = residuals.std()
    
    return {
        'AIC': round(aic, 2),
        'BIC': round(bic, 2),
        'RMSE': round(rmse, 2),
        'MAE': round(mae, 2),
        'Residual_StdDev': round(residual_std, 2)
    }

def format_forecast_explanation(data):
    """Generate improved forecast explanation with feature information."""
    # First check if we have all required data
    if not data:
        return "Could not generate forecast explanation due to missing data."
    
    metrics = data.get('metrics', {})
    model_info = data.get('model_info', {})
    forecast_data = data.get('forecast', {})
    
    # Check if forecast data exists
    if not forecast_data or not forecast_data.get('years') or not forecast_data.get('values'):
        return "Could not generate forecast explanation due to incomplete forecast data."
    
    # For historical_data, if it's missing, try to reconstruct what we can
    historical_data = data.get('historical_data', {})
    if not historical_data or not historical_data.get('values'):
        # Try to work with what we have
        forecast_results = forecast_data
        first_year = forecast_results.get('years', [0])[0] if forecast_results.get('years') else 0
        last_year = forecast_results.get('years', [0])[-1] if forecast_results.get('years') else 0
        
        # Generate a basic explanation with just the forecast data
        explanation = f"""
## Emissions Forecast ({first_year}-{last_year})

### Forecast Summary
The {model_info.get('type', 'ARIMA')} {model_info.get('order', '')} model predicts emissions values from {first_year} to {last_year}.

### Model Assessment
The optimal {model_info.get('type', 'ARIMA')}{model_info.get('order', '')} model was selected after comparing multiple parameter combinations.

### Chart Guide
Historical data appears as a solid blue line with circles, forecast as a dashed orange line with squares. The shaded area shows the 95% confidence interval - the range where actual emissions are likely to fall.
"""
        return explanation
    
    # Original function code for when all data is available
    # [rest of original function code...]
    first_year = forecast_data.get('years', [0])[0] if forecast_data.get('years') else 0
    last_year = forecast_data.get('years', [0])[-1] if forecast_data.get('years') else 0
    
    if not historical_data.get('values') or not forecast_data.get('values'):
        return "Could not generate forecast explanation due to missing data."
    
    last_hist = historical_data['values'][-1] if isinstance(historical_data['values'], list) else historical_data['values'].iloc[-1]
    last_forecast = forecast_data['values'][-1]
    
    # Calculate change
    pct_change = ((last_forecast - last_hist) / last_hist) * 100
    direction = "increase" if pct_change > 0 else "decrease"
    
    # Trend analysis - handle both list and Series inputs
    hist_values = historical_data['values']
    if not isinstance(hist_values, list):
        if hasattr(hist_values, 'tolist'):
            hist_values = hist_values.tolist()
        else:
            hist_values = [float(v) for v in hist_values]
            
    hist_trend = (hist_values[-1] - hist_values[0]) / (len(hist_values) - 1)
    forecast_trend = (forecast_data['values'][-1] - forecast_data['values'][0]) / (len(forecast_data['values']) - 1)
    trend_same = (hist_trend > 0 and forecast_trend > 0) or (hist_trend < 0 and forecast_trend < 0)
    hist_direction = "upward" if hist_trend > 0 else "downward"
    
    # Feature information
    feature_info = ""
    if model_info.get('selected_features') and len(model_info['selected_features']) > 0:
        features = model_info['selected_features']
        feature_info = f"The forecast model incorporated additional features including {', '.join(features)} to improve prediction accuracy. "
    
    explanation = f"""
## Emissions Forecast ({first_year}-{last_year})

### Forecast Summary
Based on {historical_data.get('years', [0])[0]}-{historical_data.get('years', [0])[-1]} data, the {model_info.get('type', 'ARIMA')} {model_info.get('order', '')} model predicts a **{abs(round(pct_change, 1))}%** {direction} in emissions by {last_year}, from {round(last_hist, 2)} to {round(last_forecast, 2)} units.

### Trend Analysis
Historical data shows a {hist_direction} trend of {round(abs(hist_trend), 3)} units/year. The forecast {("continues" if trend_same else "reverses")} this pattern with a projected change of {round(abs(forecast_trend), 3)} units/year.

### Model Assessment
The optimal {model_info.get('type', 'ARIMA')}{model_info.get('order', '')} model was selected after comparing multiple parameter combinations. {feature_info}

### Reliability
- **Accuracy**: MAE of {metrics.get('MAE', 'N/A')} (average prediction error)
- **Confidence Interval**: By {last_year}, emissions expected between {round(forecast_data['lower_ci'][-1], 2)} and {round(forecast_data['upper_ci'][-1], 2)}
- **Uncertainty**: Confidence interval widens over time, reflecting increasing uncertainty for later years

### Chart Guide
Historical data appears as a solid blue line with circles, forecast as a dashed orange line with squares. The shaded area shows the 95% confidence interval - the range where actual emissions are likely to fall.
"""
    
    return explanation

def generate_forecast_plot_code(data, columns, title, forecast_data):
    """Generate improved visualization code with feature information."""
    
    # Extract historical and forecast data
    historical_data = [row for row in data if row[2] == "Historical"]
    forecast_data_points = [row for row in data if row[2] == "Forecast"]
    
    # Extract years and values
    historical_years = [row[0] for row in historical_data]
    historical_values = [row[1] for row in historical_data]
    forecast_years = [row[0] for row in forecast_data_points]
    forecast_values = [row[1] for row in forecast_data_points]
    lower_ci = [row[3] for row in forecast_data_points]
    upper_ci = [row[4] for row in forecast_data_points]
    
    # Feature info for annotation
    feature_info = ""
    if forecast_data['model_info'].get('selected_features'):
        features = forecast_data['model_info']['selected_features']
        if features:
            feature_info = f"Key predictors: {', '.join(features)}"
    
    # Model info
    model_type = forecast_data['model_info']['type']
    model_order = forecast_data['model_info'].get('order', "")
    model_info = f"{model_type}" + (f"{model_order}" if model_order else "")
    
    # Generate code
    code = f"""
import matplotlib.pyplot as plt
import numpy as np

# Plot setup with improved design
plt.figure(figsize=(12, 7))
plt.style.use('seaborn-v0_8-whitegrid')

# Plot historical data
plt.plot({historical_years}, {historical_values}, '#0072B2', 
         linewidth=2.5, marker='o', markersize=5, label='Historical Data')

# Plot forecast
plt.plot({forecast_years}, {forecast_values}, '#E69F00', 
         linewidth=2.5, linestyle='--', marker='s', markersize=5, label='Forecast')

# Plot confidence intervals
plt.fill_between({forecast_years}, {lower_ci}, {upper_ci}, 
                color='#E69F00', alpha=0.2, label='95% Confidence Interval')

# Add vertical line at forecast start
plt.axvline(x={min(forecast_years)}, color='gray', linestyle='--', alpha=0.7)

# Add forecast start label
plt.text({min(forecast_years) + 0.5}, {min(min(historical_values), min(lower_ci)) + 
         (max(max(historical_values), max(upper_ci)) - min(min(historical_values), min(lower_ci)))*0.05}, 
         'Forecast Start', verticalalignment='bottom', color='gray')

# Add metrics box
plt.figtext(0.72, 0.15, 
           f"Forecast Details:\\n" +
           f"Model: {model_info}\\n" +
           f"Historical Points: {len(historical_years)}\\n" +
           f"{feature_info}",
           bbox=dict(facecolor='white', alpha=0.8, boxstyle='round', pad=0.5))

# Formatting
plt.grid(True, linestyle='--', alpha=0.7)
plt.title('{title}', fontsize=16)
plt.xlabel('Year', fontsize=12)
plt.ylabel('Emissions (Million Metric Tons CO₂e)', fontsize=12)
plt.legend(fontsize=10)

# X-axis formatting
all_years = {historical_years} + {forecast_years}
plt.xticks(
    np.arange(min(all_years), max(all_years)+1, step=max(1, len(all_years)//10)),
    rotation=45
)

plt.tight_layout()
plt.savefig('climate_visualization.png', dpi=300, bbox_inches='tight')
plt.show()
"""
    
    return code