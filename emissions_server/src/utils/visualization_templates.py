# src/utils/visualization_templates.py
"""
Visualization templates for ClimateGPT.

This module provides code templates for generating different types of plots
based on query results. These templates are used by the visualization module.
"""

import json
import logging

# Set up logging
logger = logging.getLogger('visualization_templates')

def get_line_plot_code(viz_spec):
    """Generate code for a line plot."""
    title = viz_spec["title"]
    x_axis = viz_spec["x_axis"]
    y_axes = viz_spec["y_axes"]
    columns = viz_spec["columns"]
    
    code = f"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Create DataFrame from data
data = {json.dumps(viz_spec['data'])}
columns = {json.dumps(viz_spec['columns'])}
df = pd.DataFrame(data, columns=columns)

# Explicitly define colorblind-friendly colors
# Okabe-Ito color palette - proven to be distinguishable for color vision deficiency
colorblind_colors = ['#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7', '#000000']
plt.rcParams['axes.prop_cycle'] = plt.cycler('color', colorblind_colors)

# Setup the plot
plt.figure(figsize=(10, 6))

# Create line plot
{', '.join([f'plt.plot(df["{columns[x_axis["index"]]}"], df["{columns[y["index"]]}"], label="{columns[y["index"]]}", linewidth=2.5,  marker="o", markersize=5)' for y in y_axes])}

plt.title('{title}', fontsize=14)
plt.xlabel('{x_axis["label"]}', fontsize=12)
plt.ylabel('Value', fontsize=12)
plt.grid(True, linestyle='--', alpha=0.7)
plt.legend(fontsize=10)

# Add a small text credit for accessibility
plt.figtext(0.99, 0.01, 'Colorblind-friendly palette', 
           horizontalalignment='right', fontsize=8, style='italic')

plt.tight_layout()
plt.savefig('climate_visualization.png', dpi=300, bbox_inches='tight')
plt.show()
"""
    return code

def get_bar_plot_code(viz_spec):
    """Generate code for a bar plot."""
    title = viz_spec["title"]
    x_axis = viz_spec["x_axis"]
    y_axes = viz_spec["y_axes"]
    columns = viz_spec["columns"]
    
    if len(y_axes) == 1:
        # Simple bar chart for one y-axis
        code = f"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Create DataFrame from data
data = {json.dumps(viz_spec['data'])}
columns = {json.dumps(viz_spec['columns'])}
df = pd.DataFrame(data, columns=columns)

# Explicitly define colorblind-friendly colors
colorblind_colors = ['#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7', '#000000']
plt.rcParams['axes.prop_cycle'] = plt.cycler('color', colorblind_colors)

# Setup the plot
plt.figure(figsize=(10, 6))

# Create bar plot with explicit colors
plt.bar(df["{columns[x_axis["index"]]}"], df["{columns[y_axes[0]["index"]]}"], color=colorblind_colors)

plt.title('{title}', fontsize=14)
plt.xlabel('{x_axis["label"]}', fontsize=12)
plt.ylabel('{y_axes[0]["label"]}', fontsize=12)
plt.xticks(rotation=45, ha='right')  # Rotate labels for better readability
plt.tight_layout()  # Adjust spacing for rotated labels

# Add a small text credit for accessibility
plt.figtext(0.99, 0.01, 'Colorblind-friendly palette', 
           horizontalalignment='right', fontsize=8, style='italic')

plt.savefig('climate_visualization.png', dpi=300, bbox_inches='tight')
plt.show()
"""
    else:
        # Grouped bar chart for multiple y-axes
        code = f"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Create DataFrame from data
data = {json.dumps(viz_spec['data'])}
columns = {json.dumps(viz_spec['columns'])}
df = pd.DataFrame(data, columns=columns)

# Explicitly define colorblind-friendly colors
colorblind_colors = ['#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7', '#000000']
plt.rcParams['axes.prop_cycle'] = plt.cycler('color', colorblind_colors)

# Setup the plot
plt.figure(figsize=(10, 6))

# Create grouped bar plot
x = np.arange(len(df["{columns[x_axis["index"]]}"]))
width = 0.8 / {len(y_axes)}  # the width of the bars

{chr(10).join([f'plt.bar(x + {i}*width - ({len(y_axes)-1}*width/2), df["{columns[y["index"]]}"], width, label="{columns[y["index"]]}", color=colorblind_colors[{i % 8}])' for i, y in enumerate(y_axes)])}

plt.title('{title}', fontsize=14)
plt.xlabel('{x_axis["label"]}', fontsize=12)
plt.ylabel('Value', fontsize=12)
plt.xticks(x, df["{columns[x_axis["index"]]}"], rotation=45, ha='right')
plt.legend(fontsize=10)
plt.tight_layout()  # Adjust spacing for rotated labels

# Add a small text credit for accessibility
plt.figtext(0.99, 0.01, 'Colorblind-friendly palette', 
           horizontalalignment='right', fontsize=8, style='italic')

plt.savefig('climate_visualization.png', dpi=300, bbox_inches='tight')
plt.show()
"""
    return code

def get_horizontal_bar_plot_code(viz_spec):
    """Generate code for a horizontal bar plot."""
    title = viz_spec["title"]
    x_axis = viz_spec["x_axis"]
    y_axes = viz_spec["y_axes"]
    columns = viz_spec["columns"]
    
    if len(y_axes) == 1:
        # Simple horizontal bar chart for one y-axis
        code = f"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Create DataFrame from data
data = {json.dumps(viz_spec['data'])}
columns = {json.dumps(viz_spec['columns'])}
df = pd.DataFrame(data, columns=columns)

# Explicitly define colorblind-friendly colors
colorblind_colors = ['#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7', '#000000']
plt.rcParams['axes.prop_cycle'] = plt.cycler('color', colorblind_colors)

# Setup the plot
plt.figure(figsize=(10, 6))

# Create horizontal bar plot with explicit colors
plt.barh(df["{columns[x_axis["index"]]}"], df["{columns[y_axes[0]["index"]]}"], color=colorblind_colors)

plt.title('{title}', fontsize=14)
plt.xlabel('{y_axes[0]["label"]}', fontsize=12)
plt.ylabel('{x_axis["label"]}', fontsize=12)

# Add a small text credit for accessibility
plt.figtext(0.99, 0.01, 'Colorblind-friendly palette', 
           horizontalalignment='right', fontsize=8, style='italic')

plt.tight_layout()
plt.savefig('climate_visualization.png', dpi=300, bbox_inches='tight')
plt.show()
"""
    else:
        # Grouped horizontal bar chart for multiple y-axes
        code = f"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Create DataFrame from data
data = {json.dumps(viz_spec['data'])}
columns = {json.dumps(viz_spec['columns'])}
df = pd.DataFrame(data, columns=columns)

# Explicitly define colorblind-friendly colors
colorblind_colors = ['#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7', '#000000']
plt.rcParams['axes.prop_cycle'] = plt.cycler('color', colorblind_colors)

# Setup the plot
plt.figure(figsize=(10, 6))

# Create grouped horizontal bar plot
y = np.arange(len(df["{columns[x_axis["index"]]}"]))
height = 0.8 / {len(y_axes)}  # the height of the bars

{chr(10).join([f'plt.barh(y + {i}*height - ({len(y_axes)-1}*height/2), df["{columns[y["index"]]}"], height, label="{columns[y["index"]]}", color=colorblind_colors[{i % 8}])' for i, y in enumerate(y_axes)])}

plt.title('{title}', fontsize=14)
plt.ylabel('{x_axis["label"]}', fontsize=12)
plt.xlabel('Value', fontsize=12)
plt.yticks(y, df["{columns[x_axis["index"]]}"])
plt.legend(fontsize=10)

# Add a small text credit for accessibility
plt.figtext(0.99, 0.01, 'Colorblind-friendly palette', 
           horizontalalignment='right', fontsize=8, style='italic')

plt.tight_layout()
plt.savefig('climate_visualization.png', dpi=300, bbox_inches='tight')
plt.show()
"""
    return code

def get_pie_plot_code(viz_spec):
    """Generate code for a pie chart."""
    title = viz_spec["title"]
    columns = viz_spec["columns"]
    label_index = viz_spec.get("label_index", 0)
    value_index = viz_spec.get("value_index", 1)
    
    code = f"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Create DataFrame from data
data = {json.dumps(viz_spec['data'])}
columns = {json.dumps(viz_spec['columns'])}
df = pd.DataFrame(data, columns=columns)

# Explicitly define colorblind-friendly colors
colorblind_colors = ['#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7', '#000000']
plt.rcParams['axes.prop_cycle'] = plt.cycler('color', colorblind_colors)

# Setup the plot
plt.figure(figsize=(10, 6))

# Handle negative values for pie charts - Matplotlib can't plot negative values in pie charts
value_col = "{columns[value_index]}"
label_col = "{columns[label_index]}"

# Create a copy of the data for pie chart
pie_df = df.copy()

# If there are any negative values, we need to handle them specially
if (pie_df[value_col] < 0).any():
    # Separate positive and negative values
    positive_mask = pie_df[value_col] >= 0
    negative_mask = pie_df[value_col] < 0
    
    # Keep only positive values for the pie chart
    pie_df = pie_df[positive_mask].copy()
    negative_values = df[negative_mask].copy()
    
    # Print a warning about excluded negative values
    if not negative_values.empty:
        print("Note: The following negative values were excluded from the pie chart:")
        for i, row in negative_values.iterrows():
            print(f"  - {{row[label_col]}}: {{row[value_col]}} (carbon sink/reduction)")

# Create pie chart with explicit colorblind-friendly colors
if not pie_df.empty:
    plt.pie(pie_df[value_col], labels=pie_df[label_col], 
            colors=colorblind_colors, autopct='%1.1f%%', startangle=90,
            wedgeprops={{'edgecolor': 'w', 'linewidth': 1.5}})  # Add white edge for better contrast
    
    plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
    plt.title('{title}\\n(Positive emissions only)', fontsize=14)
else:
    # If all values were negative, we can't make a pie chart
    plt.text(0.5, 0.5, "Cannot create pie chart: All values are negative", 
             horizontalalignment='center', verticalalignment='center',
             transform=plt.gca().transAxes, fontsize=14)
    plt.axis('off')

# Add a small text credit for accessibility
plt.figtext(0.99, 0.01, 'Colorblind-friendly palette', 
           horizontalalignment='right', fontsize=8, style='italic')

plt.tight_layout()
plt.savefig('climate_visualization.png', dpi=300, bbox_inches='tight')
plt.show()
"""
    return code

def get_forecast_plot_code(viz_spec):
    """Generate code for a forecast plot."""
    # If we already have custom plot code, use that
    if "plot_code" in viz_spec:
        return viz_spec["plot_code"]
    
    # Otherwise, generate a default forecast plot
    title = viz_spec["title"]
    columns = viz_spec["columns"]
    data = viz_spec["data"]
    
    # Find indices for year, emissions, and type columns
    year_idx = columns.index("year") if "year" in columns else 0
    emissions_idx = columns.index("emissions") if "emissions" in columns else 1
    type_idx = columns.index("type") if "type" in columns else 2
    lower_ci_idx = columns.index("lower_ci") if "lower_ci" in columns else None
    upper_ci_idx = columns.index("upper_ci") if "upper_ci" in columns else None
    
    # Separate historical and forecast data
    historical_data = [row for row in data if row[type_idx] == "Historical"]
    forecast_data = [row for row in data if row[type_idx] == "Forecast"]
    
    # Extract years and values
    hist_years = [row[year_idx] for row in historical_data]
    hist_values = [row[emissions_idx] for row in historical_data]
    forecast_years = [row[year_idx] for row in forecast_data]
    forecast_values = [row[emissions_idx] for row in forecast_data]
    
    # Extract confidence intervals if available
    lower_ci = None
    upper_ci = None
    if lower_ci_idx is not None and upper_ci_idx is not None:
        lower_ci = [row[lower_ci_idx] for row in forecast_data]
        upper_ci = [row[upper_ci_idx] for row in forecast_data]
    
    code = f"""
import matplotlib.pyplot as plt
import numpy as np

# Plot setup
plt.figure(figsize=(12, 7))

# Plot historical data
plt.plot({hist_years}, {hist_values}, '#0072B2', 
         linewidth=2.5, marker='o', markersize=5, label='Historical Data')

# Plot forecast
plt.plot({forecast_years}, {forecast_values}, '#E69F00', 
         linewidth=2.5, linestyle='--', marker='s', markersize=5, label='Forecast')
"""

    # Add confidence intervals if available
    if lower_ci and upper_ci:
        code += f"""
# Plot confidence intervals
plt.fill_between({forecast_years}, {lower_ci}, {upper_ci}, 
                color='#E69F00', alpha=0.2, label='95% Confidence Interval')
"""

    # Add the rest of the plot code
    code += f"""
# Add vertical line at forecast start
plt.axvline(x={max(hist_years) if hist_years else 0}, color='gray', linestyle='--', alpha=0.7)

# Add forecast start label
plt.text({max(hist_years) if hist_years else 0} + 0.5, {min(min(hist_values) if hist_values else [0], min(lower_ci) if lower_ci else [0]) + 
         (max(max(hist_values) if hist_values else [0], max(upper_ci) if upper_ci else [0]) - min(min(hist_values) if hist_values else [0], min(lower_ci) if lower_ci else [0]))*0.05}, 
         'Forecast Start', verticalalignment='bottom', color='gray')

# Formatting
plt.grid(True, linestyle='--', alpha=0.7)
plt.title('{title}', fontsize=16)
plt.xlabel('Year', fontsize=12)
plt.ylabel('Emissions', fontsize=12)
plt.legend(fontsize=10)

# X-axis formatting
all_years = {hist_years} + {forecast_years}
plt.xticks(
    np.arange(min(all_years), max(all_years)+1, step=max(1, len(all_years)//10)),
    rotation=45
)

plt.tight_layout()
plt.savefig('climate_visualization.png', dpi=300, bbox_inches='tight')
plt.show()
"""
    return code

def get_plot_code(viz_spec):
    """
    Generate the appropriate plot code based on the visualization type.
    
    Args:
        viz_spec: Visualization specification
        
    Returns:
        String containing Python code to generate the visualization
    """
    viz_type = viz_spec["type"]
    
    if viz_type == "line":
        return get_line_plot_code(viz_spec)
    elif viz_type == "bar":
        return get_bar_plot_code(viz_spec)
    elif viz_type == "bar_horizontal":
        return get_horizontal_bar_plot_code(viz_spec)
    elif viz_type == "pie":
        return get_pie_plot_code(viz_spec)
    elif viz_type == "forecast_line":
        return get_forecast_plot_code(viz_spec)
    else:
        # Default to bar chart
        logger.warning(f"Unknown visualization type: {viz_type}, defaulting to bar chart")
        return get_bar_plot_code(viz_spec)