def generate_prompt(name, crit_type, rule):
    text = f"""
You are an assistant that converts clinical trial eligibility criteria into machine-readable rules for the Flatiron Health data platform.

Instructions:
- Write the criterion name in the first row (exactly as given) and only extract the information related to the criterion name.
- Each rule starts with "#inclusion" or "#exclusion".
- Data name format: “Table[‘featurename’]”. For example, “demographics[‘gender’]”denotes column gender in table demographics..
- Operators and functions: 
    - equation operators: ==, !=, <, <=, >, >=.
    - logic operators: AND, OR. 
    - functions: MIN, MAX, ABS.
    - Example: (Table1[‘a’] == constant) AND ((Table1[‘b’] < Table2[‘c’]) OR (Table1[‘b’] < Table3[‘d’])).
- Time is encoded as “DAYS(80)”: 80 days; “MONTHS(4)”: 4 months; “YEARS(3)”: 3 years. 
    - For example, “treatment[‘date’] >= demographics[‘birthdate’] + @YEARS(18)” 
        indicates including patients more than 18 years old when they received the treatment.
- Each row is operated in sequential order.
    - The tables are prepared before the last row. For example, “treatment[‘line’]==1”
        denotes that we only use the treatment table in the first line. To avoid confusion,
        we only operate on the table in the left-hand side of the equations.
    - The patients are selected at the last row. For example, after we prepare the
        treatment table to be first line only, “treatment[‘date’] >= demographics[‘birthdate’]
        + @YEARS(18)” denotes that we include patients more than 18 years old when
        they start their first line of therapy.

Here is the Flatiron Health data dictionary to reference where the key is the table name and values are the available fields:
BaselineECOG: PatientID,ECOGSource,LineNumber,LineStartDate,ECOGValue,ECOGDate,EnhancedCohort
Demographics: PatientID,BirthYear,BirthSex,Race,Ethnicity,State  
Diagnosis: PatientID,PracticeID,DiagnosisDate,DiagnosisCode,DiagnosisCodeSystem,DiagnosisDescription
DrugEpisode: PatientID,LineName,LineNumber,LineSetting,IsMaintenanceTherapy,EnhancedCohort,LineStartDate,LineEndDate,EpisodeDate,EpisodeDataSource,DrugName,Amount,Units,DrugCategory,DetailedDrugCategory,Route
ECOG:PatientID,PracticeID,EcogDate,EcogValue
EnhancedCohort: PatientID, EnhancedCohort 
Enhanced_AdvNSCLCBiomarkers: PatientID,BiomarkerName,CellType,SpecimenCollectedDate,SpecimenReceivedDate,ResultDate,BiomarkerStatus,ExpressionLevel,BiomarkerDetail,SampleType,TissueCollectionSite,TestType,LabName,Assay,IHCClone,StainingIntensity,PercentStaining,CombinedPositiveScore
Enhanced_AdvNSCLC_Orals: PatientID,DrugName,StartDate,EndDate,DateGranularity 
Enhanced_AdvNSCLC_Progression: PatientID,ProgressionDate,ProgressionDateGranularity,IsRadiographicEvidence,IsPathologicEvidence,IsClinicalAssessmentOnly,IsMixedResponse,IsPseudoprogressionMentioned,LastClinicNoteDate
Enhanced_AdvancedNSCLC: PatientID,DiagnosisDate,AdvancedDiagnosisDate,Histology,GroupStage,SmokingStatus 
Enhanced_Mortality_V2: PatientID, DateOfDeath
ExtractedMetastaticDiagnosis: PatientID,IsMetastatic,MetastaticDxDate
Insurance: PatientID,PracticeID,PayerCategory,StartDate,EndDate,IsMedicareAdv,IsMedicareSupp,IsPartAOnly,IsPartBOnly,IsPartAandPartB,IsPartDOnly,IsManagedGovtPlan,IsManagedMedicaid,IsMedicareMedicaid
Lab: PatientID,PracticeID,TestDate,LOINC,Test,LabComponent,TestBaseName,LabSource,TestUnits,ResultDate,TestResult,MinNorm,MaxNorm
LineOfTherapy: PatientID,LineName,LineNumber,LineSetting,RegimenClass,IsMaintenanceTherapy,EnhancedCohort,StartDate,EndDate
MedicationAdministration: PatientID,PracticeID,OrderID,DrugName,CommonDrugName,Route,DrugCategory,DetailedDrugCategory,AdministeredDate,AdministeredAmount,AdministeredUnits
MedicationOrder: PatientID,PracticeID,OrderID,OrderedDate,ExpectedStartDate,OrderedAmount,OrderedUnits,RelativeOrderedAmount,RelativeOrderedUnits,DrugName,CommonDrugName,DrugCategory,DetailedDrugCategory,Route,Quantity,QuantityUnits,Refill,PlannedCycles,IsCanceled
Practice: PatientID,PracticeID,PracticeType,PrimaryPhysicianID  
SocialDeterminantsOfHealth: PatientID,SESIndex2015_2019
Telemedicine:PatientID,PracticeID,VisitDate
Visit: PatientID,PracticeID,VisitDate,VisitType,IsVitalsVisit,IsTreatmentVisit,IsLabVisit
Vitals: PatientID,PracticeID,TestDate,LOINC,Test,LabComponent,TestBaseName,TestUnits,ResultDate,TestResult,MinNorm,MaxNorm
---
Examples:

- Example 1:
Input:
Criterion Name: Age  
Criterion Type: Inclusion
Criterion Text: Male or female, aged at least 18 years. Patients from Japan aged at least 20 years.

Output:
"Age
#inclusion
(lineoftherapy['linenumber']==1) AND (lineoftherapy['ismaintenancetherapy']==False)
(lineoftherapy['startdate'] >= demographics['birthyear'] + @YEARS(18))"

- Example 2:
Input:
Criterion Name: ALT  
Criterion Type: Exclusion
Criterion Text: Alanine aminotransferase (ALT) >2.5x the upper limit of normal (ULN) if no demonstrable liver metastases or >5xULN in the presence of liver metastases.

Output:
"ALT
#inclusion
(lineoftherapy['linenumber']==1) AND (lineoftherapy['ismaintenancetherapy']==False)
lab['labcomponent'] == 'Alanine aminotransferase (ALT or SGPT)' 
(lab[‘testdate’] >= lineoftherapy['startdate'] - @DAYS(28) ) AND (lab[‘testdate’] <= lineoftherapy['startdate'])
MIN(ABS(lab[‘testdate’] -lineoftherapy['startdate']))
lab['testresultcleaned'] <= 2.5 * lab['maxnormcleaned']"

- Example 3:
Input:
Criterion Name: ECOG  
Criterion Type: Inclusion
Criterion Text: World Health Organization Performance Status of 0 to 1 with no clinically significant deterioration over the previous 2 weeks and a minimum life expectancy of 12 weeks.

Output:
"ECOG
#Inclusion
(lineoftherapy['linenumber']==1) AND (lineoftherapy['ismaintenancetherapy']==False)
(ecog[‘ecogdate’] >= lineoftherapy['startdate'] - @DAYS(30) ) AND (ecog[‘ecogdate’] <= lineoftherapy['startdate'] + @DAYS(7) )
MIN(ABS(ecog[‘ecogdate’] - enhanced_advancednsclc[‘advanceddiagnosisdate’] ))
(ecog['ecogvalue'] == 0) OR (ecog['ecogvalue'] == 1)"

- Example 4:
Input:
Criterion Name: Histology_NonSquamous  
Criterion Type: Inclusion
Criterion Text: Histologically or cytologically documented inoperable, locally advanced (Stage IIIb who are not amenable for combined modality treatment), metastatic (Stage IV), or recurrent non-squamous NSCLC. Diagnoses of non-squamous NSCLC that are based on sputum cytology alone are not acceptable. Mixed tumors should be categorized according to the predominant cell type.

Output:
"Histology_NonSquamous
#inclusion
(enhanced_advancednsclc['histology'] == 'Non-squamous cell carcinoma')"

- Example 5:
Input:
Criterion Name: Staging  
Criterion Type: Inclusion
Criterion Text: Pathologically confirmed adenocarcinoma of the lung (e.g., this may occur as systemic recurrence after prior surgery for early stage disease or patients may be newly diagnosed with Stage IIIB/IV disease). Patients with mixed histology are eligible if adenocarcinoma
is the predominant histology.

Output:
"Staging
#inclusion
(enhanced_advancednsclc['groupstage'] == 'Stage IIIB' OR enhanced_advancednsclc['groupstage'] == 'Stage IV')"

- Example 6:
Input:
Criterion Name: Platelets  
Criterion Type: Exclusion
Criterion Text: Platelet count <100 x 109/L.

Output:
"Platelets
#inclusion
(lineoftherapy['linenumber']==1) AND (lineoftherapy['ismaintenancetherapy']==False)
lab['labcomponent'] == 'Platelet count' 
(lab[‘testdate’] >= lineoftherapy['startdate'] - @DAYS(28) ) AND (lab[‘testdate’] <= lineoftherapy['startdate'])
MIN(ABS(lab[‘testdate’] - lineoftherapy['startdate']))
lab['testresultcleaned'] >= 100"

---

Now transform the following:

Criterion Name: {name}  
Criterion Type: {crit_type}
Criterion Text: {rule}
"""
    return text