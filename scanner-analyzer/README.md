Databricks Discovery & Analysis Utility – Setup Guide (Work In Progress)  
📘 Assets Information  
https://github.com/customer-success-microsoft/Trinity-Framework/tree/main/AzureDatabricks-Utilities

Owners:

Amit Damle (amitdamle@microsoft.com)  
RK Iyer (raiy@microsoft.com)  
Reviewers (In Progress):

Shivani Tripathi (tripathishi@microsoft.com)

This README converts the provided SetupInstructions.docx into a clean, reusable Markdown guide.

1.  Extract Package  
    Extract the provided zip file on your local machine. It will create the following directory structure:

dbx-scaner-analysis-util/  
├── config/  
├── dashboard/  
├── dist/  
├── notebooks/  
2\. Databricks Prerequisites  
Log in to your Databricks Workspace as a Workspace / Account Admin  
Create:  
External Location  
Volume (using the external location)  
3\. Prepare Volume Structure  
In the created volume, create a folder named script  
Copy the following into the script folder:  
Wheel file from the dist folder  
analyzer\_rules.json from the config folder  
4\. Import Notebooks  
Copy the notebooks from the notebooks folder  
Import them into your Databricks workspace  
5\. Cluster Setup  
Create a Single Node Spark Cluster  
This cluster will be used to execute all Python notebooks  
6\. Discovery Setup  
Open 00\_discovery\_Setup.py  
Update MANAGED LOCATION:  
Use an existing catalog or  
Create a new catalog using the external location  
Execute all cells  
This creates discovery scan tables used by dashboards  
7\. Run Discovery Notebook  
Open 01\_discovery\_notebook.ipynb  
Update the wheel file path (same as step 3)  
In Cell 3, update the following parameters:  
WORKSPACE\_URL  
DISCOVERY\_OUTPUT # out folder path + /discovery  
CATALOG\_NAME  
SCHEMA\_NAME  
Keep all other parameters unchanged  
Attach the notebook to the cluster  
Execute all cells  
8\. Import Dashboard  
From the dashboard folder, import:  
Databricks Discovery.lvdash.json  
After import:  
Go to the Data tab  
Set the workspace\_id  
If using a different catalog or schema, update all queries accordingly  
9\. Discovery Output  
After successful execution:

Volume Output:  
out/discovery will contain discovery artifacts  
Dashboard:  
Displays counts of clusters, jobs, pipelines, notebooks, UC objects, etc.  
10\. Generate Analysis  
Open 02\_generate\_all\_analysis.ipynb  
Update parameters:  
RULES\_PATH # analyzer\_rules.json location  
DISCOVERY\_OUTPUT # out folder path + /discovery  
ANALYSIS\_OUTPUT # out folder path + /analysis  
Attach to the existing cluster  
Execute all cells  
✅ Output: analysis folder with generated artifacts

Generate Insights (Optional)  
Open 03\_generate\_insights.ipynb  
Update:  
ANALYSIS\_FOLDER\_PATH  
Attach to running cluster  
Execute all cells  
✅ Charts and insights will be generated from analysis files

Final Outcome  
Discovery artifacts stored in volume  
Analysis reports generated  
Interactive dashboards and charts available in Databricks