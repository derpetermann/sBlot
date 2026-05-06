[← Back to documentation](../index.md)

# Weight plots

Weight plots visualise the posterior densities of the weights per feature: how well does each 
component - the confounders and the clustering – explain the distribution of the feature in the 
data? For example, a language analysis will likely have two confounders: inheritance and universal preference.
In this case, the weights are displayed in a triangular probability simplex. The lower right corner is the weight for inheritance 
(I), the upper corner is the weight for universal preference (U), and the lower 
left corner is the cluster weight (C). The figure below shows the weight plots for two features, F24 and F16. Inheritance and clustering best explain the distribution of F24, whereas F26 has no single 
dominant explanation: the posterior weights are broadly distributed. The pink dot marks the 
mean of the distribution. As with other plot types, `sBlot` returns the density 
plots for all features in a single grid.

<div style="text-align: center;">
    <img style="border-radius: 0.3125em;
    box-shadow: 0 2px 4px 0 rgba(34,36,38,.12),0 2px 10px 0 rgba(34,36,38,.08);" 
    src="../images/weights.png" alt="Weight plots for features F24 and F16.">
    <br>
    <div style="color: black; border-bottom: 1px solid #d9d9d9;
    display: inline-block;
    padding: 2px;">Weight plots for two features (F24, F16)</div>
</div>

#### Further reading:

- [How to set up weight plots in **`config_plot.yaml`**](../configuration/config_plot.md#weight-plots-plotsweights)
- [How to change the appearance of weight plots in **`config_style.yaml`**](../configuration/config_style.md#weight-plots-weights)
- [How to render weight plots](../quickstart.md#weight-plots)