[← Back to documentation](../index.md)

# Plot types

sBlot provides five types of plots for visualising the results of an sBayes analysis.

## Weight plots

[Weight plots](weights.md) visualise the posterior distribution of weights per feature — how well does each component (the confounders and the clustering) explain the distribution of the feature in the data? Weights are displayed as density plots in a probability simplex, with one panel per feature arranged in a grid.


## Preference plots

[Preference plots](preferences.md) show the posterior distribution of feature state preferences for each component — the cluster effect and each group within each confounder. One grid of simplex panels is generated per component, with one panel per feature.


## Pie plots

[Pie plots](pies.md) show how often each object is assigned to each cluster in the posterior. Each slice of the pie represents the fraction of posterior samples in which the object was assigned to a given cluster.


## LOO plots

[LOO plots](loo.md) compare the expected predictive performance across models with different numbers of clusters, helping users choose an appropriate value of K. As a rule of thumb, the preferred model is the one beyond which improvements in predictive performance become negligible.


## Maps

[Maps](map.md) visualise the geographic distribution of posterior cluster assignments. Three map types are available:

- **Line maps** connect neighbouring objects in the same cluster with lines. Line thickness indicates how often two objects are assigned to the same cluster.
- **Pie maps** Pie plots on a map. Color each object by its cluster assignment.
- **IDW maps** produce a spatially interpolated color field showing cluster influence across the map area.

