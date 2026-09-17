# Lab 2 — Run comparison

Experiment `itcs355-lab2` · 12 trials · total spend 0.4190 THB

`thb_per_point` is cost per percentage point of val_roc_auc above the worst trial. Cheap improvements rank low; expensive improvements rank high, however good the headline number is.

| run_id | val_roc_auc | cost_thb | n_estimators | max_depth | min_samples_leaf | thb_per_point |
| --- | --- | --- | --- | --- | --- | --- |
| fff19929 | 0.8426 | 0.0325 | 100 | 4 | 5 | 0.0201 |
| 5b176ec4 | 0.8424 | 0.032 | 100 | 4 | 1 | 0.0201 |
| d6b79aa6 | 0.8411 | 0.032 | 300 | 4 | 5 | 0.0219 |
| 59f5fb5c | 0.8404 | 0.032 | 300 | 4 | 1 | 0.023 |
| 26dcb4a9 | 0.8397 | 0.0325 | 100 | 8 | 5 | 0.0245 |
| d12b09be | 0.8377 | 0.0325 | 300 | 8 | 5 | 0.0289 |
| 5cb39caa | 0.8354 | 0.0325 | 300 | 12 | 5 | 0.0364 |
| 30a170c8 | 0.8338 | 0.032 | 300 | 8 | 1 | 0.0436 |
| 26a13339 | 0.8322 | 0.032 | 100 | 12 | 5 | 0.0558 |
| 8e21ce55 | 0.8312 | 0.0325 | 100 | 8 | 1 | 0.0686 |
| 087526d7 | 0.8268 | 0.0485 | 100 | 12 | 1 | 1.4332 |
| 092f6c87 | 0.8265 | 0.048 | 300 | 12 | 1 | 12.4999 |

## Which model did you register, and why?

1. I choose the Random Forest with 100 estimators, a maximum depth of 4, and a minimum leaf size of 5. It achieved the highest validation ROC-AUC in the main study at 0.8426, with an estimated training cost of only 0.0325 THB. Although its score was the highest, the difference from the second-best model was only 0.0002. I therefore also considered its lower complexity and cost compared with the 300-tree models.

2. I tested the same configuration using three seeds. The mean validation ROC-AUC was 0.846551, with a standard deviation of 0.002842 and a range of 0.006563. Since this variation is larger than the gap between the two best trials, the ranking may not always remain the same.

3. Retraining this model once per month should cost approximately 0.0325 THB per month. Running the complete 12-trial study again would cost around 0.4190 THB.

4. This model could still be the wrong choice if future machines or sensor readings have a different distribution from the validation data. Its performance should therefore be monitored after deployment.
