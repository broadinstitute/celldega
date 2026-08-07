# Cloud Environments

Spatial-omics datasets are large, and the compute needed to process and visualize
them is often best run in the cloud. Celldega is designed to run in cloud
environments so that researchers can generate, store, and interactively explore
[LandscapeFiles](../overview/file_formats.md#landscapefiles) close to where their
data already lives — without moving large datasets to a local machine.

We have built and are actively developing implementations across multiple cloud
platforms:

- **[Terra.bio](https://app.terra.bio/)** — A cloud-based compute and data platform
  developed at the <a href="https://www.broadinstitute.org/spatial-technology-platform" target="_blank">Broad Institute</a>.
  We have built implementations on Terra.bio for running Celldega workflows, including
  cell segmentation and generating LandscapeFiles directly from a Terra workspace.

- **[Manifold.ai](https://www.manifold.ai/)** — We are actively working with Manifold
  to deploy Celldega, enabling workflow submission to AWS HealthOmics from a managed
  Jupyter Notebook environment.

## Topics

### Terra.bio

- [Cell Segmentation on Terra](Terra/Cell_Segmentation_on_Terra.md) — Run WDL-based
  cell segmentation workflows (e.g., Cellpose, Instanseg) on Terra.
- [Generating LandscapeFiles on Terra](Terra/Generating_LandscapeFiles.md) — Launch the
  `stp_celldega_landscape_files` workflow from Terra to produce LandscapeFiles for
  visualization.

### Manifold.ai

- [Generating LandscapeFiles on Manifold](Manifold/Generating_LandscapeFiles.md) — Submit
  the LandscapeFiles WDL workflow via AWS HealthOmics from a Manifold notebook environment.
