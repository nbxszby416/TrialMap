### analysis for TrialMap paper

library(dplyr)
library(janitor)
library(debiasedTrialEmulation)
library(EmpiricalCalibration)
library(data.table)

source("source_TrialMap.R")
df = read.csv("demo_data.csv")

### process outcome column
outcome_columns <- c("DeathDate", colnames(df %>% select(starts_with("nco_"))))
df <- create_survival_columns(df, outcome_columns)

xvars <- c('Age', 'BirthSex', 'Race_Ethnicity', 'SESIndex2015_2019', 'Region',
           'StageCategory', 'EcogValue', 'InsuranceCategory', 
           'SmokingStatus', 'PracticeType', 'TeleMedicineUse',
           colnames(df %>% select(starts_with("medical_"))),
           'BiomarkerPDL1PercentStaining') %>% make_clean_names()
yvars <- c('event_DeathDate') %>% make_clean_names()
ncovars <- colnames(df %>% select(starts_with("event_nco_")))

criteria_cols <- c("pass_ECOG", "pass_CNS_metastasis", "pass_Hemoglobin")

subgroups <- generate_subgroups(criteria_cols)

rslt_sub00 <- dTTE(df, xvars, yvars, ncovars, ps0="C0")
ps0 <- rslt_sub00$ps
c_sub00 <- data.frame(subgroup_id="C0", n_criteria=0, criteria="", criteria_item="")
fwrite(cbind(c_sub00, rslt_sub00$rslt), file="demo_results.csv", row.names = FALSE, append = T)

for (i in 2:nrow(subgroups)) {
  cat("This is the ", i, "-th subgroup \n")
  criteria <- strsplit(subgroups$criteria, "\\, ")[[i]]
  df_sub <- df[rowSums(df[criteria]) == length(criteria), ]
  
  rslt_sub <- dTTE(df_sub, xvars, yvars, ncovars, ps0)
  
  c_sub <- subgroups[i,]
  c_sub$criteria <- gsub("passes_", "", c_sub$criteria)
  
  fwrite(cbind(c_sub, rslt_sub$rslt), file="demo_results.csv", row.names = FALSE, append = T)
}

rslt <- read.csv("demo_results.csv")

front_3d_os <- pareto_front_3obj(rslt$logHR_cal_OS, -rslt$n, rslt$AE_new_onset_PP)

rslt_pareto_os <- rslt[front_3d_os, ]
rslt_pareto_os$pareto_front_os <- 1
rslt_pareto_os$SUCRA_OS <- sucra(rslt_pareto_os$logHR_cal_OS, rslt_pareto_os$seLogHR_cal_OS, seed = 1)
rslt_pareto_os <- rslt_pareto_os[order(rslt_pareto_os$SUCRA_OS, decreasing = TRUE), ]

rslt_non_pareto_os <- rslt[-front_3d_os, ]
rslt_non_pareto_os$pareto_front_os <- 0
rslt_non_pareto_os$SUCRA_OS <- sucra(rslt_non_pareto_os$logHR_cal_OS, rslt_non_pareto_os$seLogHR_cal_OS, seed = 1)

rslt_os <- rbind(rslt_pareto_os, rslt_non_pareto_os)

write.csv(rslt_os, "demo_results_ranked.csv", row.names = FALSE)



