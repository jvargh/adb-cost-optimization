Using the attached **Azure Databricks Cost Optimization End-to-End Specification** as the authoritative baseline for all functionality already implemented, build a polished UI application on top of the existing assessment toolkit. Do not replace or duplicate the current PowerShell/Python assessment logic unless required for UI integration.

All files, source code, configuration, assets, documentation, tests, mockups, and other artifacts created specifically for this UI initiative must be placed under a new:

`/ui`

folder.

Keep the existing assessment implementation unchanged wherever possible and treat the existing collectors, models, detectors, configuration contracts, persisted run artifacts, and reporting pipeline as the backend source of truth.

### Phase 1: Build an End-to-End Mock First

Before starting the full production implementation, create an end-to-end functional mock/prototype that demonstrates the complete intended user journey using representative or mock data.

The prototype must cover the full workflow:

*   **Configure**
*   **Validate**
*   **Run Analysis**
*   **Monitor**
*   **Visualize Results**
*   **Review**
*   **Export**

The mock should be detailed enough for human reviewers to evaluate the complete user experience, including:

*   Major screens and navigation
*   Configuration flows
*   Validation states
*   Analysis execution flow
*   Progress and status indicators
*   Success, warning, partial, and failure scenarios
*   Charts, KPI cards, tables, and other appropriate visualizations
*   Filtering and drill-down behavior
*   Evidence and finding details
*   Review and export experience

### Mandatory Human Approval Gate

Once the end-to-end mock is complete, **stop development and require explicit human validation and approval**.

Do not begin the full production UI implementation until approval has been obtained.

Any feedback from the human review must first be incorporated into the mock/design and revalidated as necessary. Only the approved design should become the basis for production development.

The required delivery flow is therefore:

**Mock / Prototype → Human Review → Approval → Production UI Implementation**

### Phase 2: Production UI

After human approval, implement the production UI and organize the functionality into the following primary areas.

#### 1\. Configure

Provide an intuitive interface for defining the assessment scope and supported configuration, including where applicable:

*   Azure subscriptions
*   Resource groups
*   Azure Databricks workspaces
*   Analysis date range
*   Cost basis
*   Optional SQL Warehouse access and approval
*   Deep-dive targets
*   Output location
*   Other supported assessment settings

The UI should validate configuration before execution and clearly identify missing prerequisites, invalid selections, permission issues, safety constraints, and configuration warnings.

#### 2\. Run Analysis

Provide a guided interface for running the existing read-only assessment workflow.

The experience should:

*   Display the selected scope and effective configuration before execution
*   Launch the existing assessment backend rather than reimplementing its logic
*   Show progress across collection, normalization, analysis, findings, and report generation
*   Display collector and source status
*   Surface warnings and telemetry gaps
*   Clearly distinguish successful, partial, skipped, pending, and failed sources
*   Display meaningful errors without masking incomplete evidence
*   Show completion status and resulting assessment run
*   Allow users to open or rerun persisted assessments where the existing toolkit supports it

#### 3\. Visualize Results

Build an executive and technical analysis experience that uses the visualization format best suited to the underlying data rather than forcing all results into the same chart type.

Where appropriate, use:

*   KPI cards
*   Trend charts
*   Ranked bar charts
*   Cost breakdowns
*   Tables
*   Distributions
*   Attribution views
*   Compute analysis
*   SQL Warehouse and query analysis
*   Workload findings
*   Telemetry-quality indicators
*   Evidence-gap views
*   Prioritized optimization opportunities
*   Benefits baselines
*   30/60/90-day roadmap views

Support filtering and drill-down using relevant dimensions such as:

*   Subscription
*   Resource group
*   Workspace
*   Workload
*   Domain
*   Finding category
*   Confidence
*   Status

Users should be able to move from high-level summaries into the supporting findings and evidence, inspect detailed records where useful, and access the existing consolidated Markdown report and CSV outputs.

### UI Architecture and Organization

Structure the `/ui` implementation so that the major concerns remain modular and maintainable.

At minimum, separate logical areas for:

*   Configuration
*   Analysis execution and orchestration
*   Results visualization
*   Backend/API integration
*   Shared components
*   State management
*   Models/types
*   Testing
*   Mock/prototype assets
*   UI documentation

The UI should act as an orchestration and visualization layer over the existing assessment capability rather than creating a second independent assessment engine.

### Guardrails

Preserve all existing assessment guardrails defined in the specification, including:

*   Read-only assessment behavior
*   Scope isolation
*   SQL Warehouse auto-start approval requirements
*   Security and authentication boundaries
*   Evidence-quality handling
*   Explicit partial and failed source reporting
*   Human validation requirements
*   No unsupported savings claims
*   No automatic remediation or production changes

### Target End-State

The final approved production experience should provide a clear and intuitive end-to-end workflow:

**Configure → Validate → Run Analysis → Monitor → Visualize → Review → Export**

The objective is to transform the existing command-line assessment capability into a customer-ready UI experience while preserving the existing backend implementation, evidence model, safety boundaries, and assessment integrity.