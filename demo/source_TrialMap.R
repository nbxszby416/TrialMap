### source functions

## data pre-processing
create_survival_columns <- function(df, outcome_cols, start_date = "StartDate", end_date = "EarlierEndDate") {
  df <- df %>%
    mutate(!!start_date := as.Date(.data[[start_date]]))
  
  if (is.character(end_date) && end_date %in% names(df)) {
    df <- df %>%
      mutate(!!end_date := as.Date(.data[[end_date]]))
    use_column <- TRUE
  } else {
    end_date_value <- as.Date(end_date)
    use_column <- FALSE
  }
  
  for (col in outcome_cols) {
    time_col <- paste0("time_", col)
    event_col <- paste0("event_", col)
    
    if (use_column) {
      # Use column from dataframe
      df <- df %>%
        mutate(
          !!col := as.Date(.data[[col]]),
          !!time_col := as.numeric(pmin(.data[[col]], .data[[end_date]], na.rm = TRUE) - .data[[start_date]]),
          !!event_col := ifelse(is.na(.data[[col]]) | .data[[col]] > .data[[end_date]], 0, 1)
        )
    } else {
      # Use fixed date value
      df <- df %>%
        mutate(
          !!col := as.Date(.data[[col]]),
          !!time_col := as.numeric(pmin(.data[[col]], end_date_value, na.rm = TRUE) - .data[[start_date]]),
          !!event_col := ifelse(is.na(.data[[col]]) | .data[[col]] > end_date_value, 0, 1)
        )
    }
  }
  
  return(df)
}


# Function to calculate G-index
calculate_g_index <- function(ps_no_restrict, ps_tm) {
  f_pop <- density(ps_no_restrict, na.rm = TRUE)
  f_trial <- density(ps_tm, na.rm = TRUE)
  
  x_min <- max(min(f_pop$x), min(f_trial$x))
  x_max <- min(max(f_pop$x), max(f_trial$x))
  x_grid <- seq(x_min, x_max, length.out = 512)
  
  f_pop_interp <- approx(f_pop$x, f_pop$y, xout = x_grid)$y
  f_trial_interp <- approx(f_trial$x, f_trial$y, xout = x_grid)$y
  
  f_pop_interp[is.na(f_pop_interp)] <- 0
  f_trial_interp[is.na(f_trial_interp)] <- 0
  
  integrand <- pmin(f_pop_interp, f_trial_interp)
  g_index <- sum(integrand) * (x_grid[2] - x_grid[1])
  
  return(g_index)
}


## generate subgroup
generate_subgroups <- function(criteria_relaxed) {
  n <- length(criteria_relaxed)
  
  # Initialize with C0 (no relaxed criteria applied)
  subgroups <- data.frame(
    subgroup_id = "C0",
    n_criteria = 0,
    criteria = "",
    criteria_item = ""
  )
  
  # Generate all combinations of relaxed criteria
  for (i in 1:(2^n - 1)) {
    binary <- as.integer(intToBits(i))[1:n]
    selected_criteria <- criteria_relaxed[binary == 1]
    selected_numbers <- which(binary == 1)
    
    subgroup_row <- data.frame(
      subgroup_id = paste0("C", i),
      n_criteria = length(selected_criteria),
      criteria = paste(selected_criteria, collapse = ", "),
      criteria_item = paste(selected_numbers, collapse = ", ")
    )
    
    subgroups <- rbind(subgroups, subgroup_row)
  }
  
  return(subgroups)
}

### function to run dTTE on each subpopulation
dTTE <- function(df, xvars, yvars, ncovars, ps0) {
  tte_result <- TTE_pipeline(df, 
                             xvars = xvars, 
                             yvars = yvars, 
                             ncovars = ncovars,
                             ps_type = "Stratification", 
                             outcome_measure = "HR")
  
  fitnull <- fitNull(tte_result$df_rslt_nco$logEst, tte_result$df_rslt_nco$seLogEst)
  p.ease <- plotCalibrationEffect(logRrNegatives = tte_result$df_rslt_nco$logEst,
                                  seLogRrNegatives = tte_result$df_rslt_nco$seLogEst,
                                  showExpectedAbsoluteSystematicError = TRUE,
                                  null = fitnull)
  
  model <- fitSystematicErrorModel(tte_result$df_rslt_nco$logEst, tte_result$df_rslt_nco$seLogEst, rep(0, length(tte_result$df_rslt_nco$logEst)))
  res.cal <- calibrateConfidenceInterval(logRr = tte_result$df_rslt$logEst,
                                         seLogRr= tte_result$df_rslt$seLogEst,
                                         model, ciWidth = 0.95)
  
  logHR_uncal_OS <- tte_result$df_rslt$logEst[1]
  seLogHR_uncal_OS <- tte_result$df_rslt$seLogEst[1]
  logHR_cal_OS <- res.cal$logRr[1]
  seLogHR_cal_OS <- res.cal$seLogRr[1]
  
  df <- df %>%
    mutate(new_onset_irAE_PP = ifelse(irAE_baseline_binary == 0 & 
                                        irAE != "" & 
                                        !is.na(irAE) & 
                                        (as.Date(irAE) <= EarlierEndDate | (irAE=="")), 1, 0))

  AE_new_onset_PP <- df %>%
    filter(irAE_baseline_binary == 0) %>%
    summarise(new_onset_rate_PP = mean(new_onset_irAE_PP)) %>%
    .$new_onset_rate_PP
  
  n <- nrow(df)
  EASE <- computeExpectedAbsoluteSystematicError(fitnull)
  if (identical(ps0, "C0")){
    gindex <- 1
  }else{
    gindex <- calculate_g_index(tte_result$res$stratifiedPop$propensityScore, ps0)
  }
  
  rslt <- data.frame(logHR_uncal_OS = logHR_uncal_OS,
                     seLogHR_uncal_OS = seLogHR_uncal_OS,
                     logHR_cal_OS = logHR_cal_OS,
                     seLogHR_cal_OS = seLogHR_cal_OS,
                     n = n,
                     AE_new_onset_PP = AE_new_onset_PP,
                     EASE = EASE,
                     gindex = gindex,
                     fitnull_mean = fitnull[1],
                     fitnull_sd = fitnull[2],
                     n_nco = nrow(tte_result$df_rslt_nco))
  
  return(list(rslt=rslt, ps=tte_result$res$stratifiedPop$propensityScore))
}


### sucra
sucra <- function(logHR, seLogHR, n_sims = 10000, seed = 1) {
  set.seed(seed)
  n <- length(logHR)
  sims <- replicate(n_sims, rank(rnorm(n, logHR, seLogHR)))
  apply(sims, 1, function(r) mean(cumsum(tabulate(r, n))[1:(n-1)]) / (n-1))
}


pareto_front_3obj <- function(a, b, c) {
  n <- length(a)
  pareto_idx <- integer(0)
  
  for (i in seq_len(n)) {
    dominated <- FALSE
    for (j in seq_len(n)) {
      # j dominates i if j <= i in ALL objectives AND < in at least one
      if ((a[j] <= a[i] && b[j] <= b[i] && c[j] <= c[i]) &&
          (a[j] < a[i] || b[j] < b[i] || c[j] < c[i])) {
        dominated <- TRUE
        break
      }
    }
    if (!dominated) {
      pareto_idx <- c(pareto_idx, i)
    }
  }
  
  return(pareto_idx)
}

