% Mean energy-flux comparison using one consistent reference normalization.
% Existing Gaussian code data use epsilon_ref=0.0928 and eta_ref=0.00287.

clear

epsilon_ref = 0.0928;
eta_ref = 0.00287;
N = 1024;
L = 2*pi;
dx = L/N;

% Existing Gaussian results.  For the Gaussian filter,
% r_eq = sqrt(12)*sigma_G*dx.
r_eta = [14.8121681530451
         37.0304203826128
         74.0608407652256
         148.121681530451
         296.243363060902
         740.608407652256];
flux_eps = [0.6424, 0.8853, 0.9511, 0.9605, 0.8905, 0.5577];

% Reference curve from the paper.
r_eta_sample = [4, 8, 13, 17, 25, 40, 80, 120, 180, 250, 400, 700, 1300, 1600];
flux_eps_sample = [0.012, 0.20, 0.55, 0.72, 0.95, 1.25, 1.35, ...
                   1.40, 1.40, 1.38, 1.30, 1.15, 0.75, 0.45];

% Smooth-sharp filter: match its half-gain cutoff to a Gaussian filter.
% exp(-sigma_G^2*k_c^2/2)=1/2 and k_c=pi/(sigma_sharp*dx), hence
% sigma_G = sqrt(2*log(2))/pi * sigma_sharp.
sharp_to_gaussian_sigma = sqrt(2*log(2))/pi;

% Fixed edge width w=2*Delta k.
sigma_sharp_w2 = [10, 15, 30, 55, 75];
sigma_gaussian_eq_w2 = sharp_to_gaussian_sigma .* sigma_sharp_w2;
r_eta_w2 = sqrt(12) .* sigma_gaussian_eq_w2 .* dx ./ eta_ref;
mean_forward_pi_w2 = [0.07168550570921284, ...
                      0.08110958227896753, ...
                      0.08842126284609503, ...
                      0.09226660845542499, ...
                      0.09168732679371600];
flux_eps_w2 = mean_forward_pi_w2 ./ epsilon_ref;

% Scale-invariant edge width alpha=w/k_c=0.1171875.
% sigma=30 is an exact equivalent-filter anchor: alpha*k_c/Delta k=2,
% so it reuses the fixed-w result without claiming a second computation.
sigma_sharp_alpha = [10, 15, 30, 55];
sigma_gaussian_eq_alpha = sharp_to_gaussian_sigma .* sigma_sharp_alpha;
r_eta_alpha = sqrt(12) .* sigma_gaussian_eq_alpha .* dx ./ eta_ref;
mean_forward_pi_alpha = [0.07298069178715223, ...
                         0.08168576383672087, ...
                         0.08842126284609503, ...
                         0.09192399277249715];
flux_eps_alpha = mean_forward_pi_alpha ./ epsilon_ref;

figure
loglog(r_eta, flux_eps, '*-', 'Color', 'b', 'MarkerFaceColor', 'w', ...
    'MarkerSize', 6, 'LineWidth', 1)
hold on
loglog(r_eta_sample, flux_eps_sample, 'o-', 'Color', 'g', 'MarkerFaceColor', 'w', ...
    'MarkerSize', 6, 'LineWidth', 1)
loglog(r_eta_w2, flux_eps_w2, 's-', 'Color', [0.85, 0.20, 0.15], ...
    'MarkerFaceColor', 'w', 'MarkerSize', 6, 'LineWidth', 1)
loglog(r_eta_alpha, flux_eps_alpha, 'd-', 'Color', [0.65, 0.15, 0.75], ...
    'MarkerFaceColor', 'w', 'MarkerSize', 6, 'LineWidth', 1)
yline(1, 'k--', 'LineWidth', 1)
hold off

legend("Gaussian code", "paper", "smooth-sharp: w=2\Delta k", ...
       "smooth-sharp: \alpha=0.1171875", "ideal plateau", ...
       'Location', 'best')

xlabel('$r_{eq}/\eta$', 'Interpreter', 'latex', 'FontSize', 14)
ylabel('$\langle\Pi_{forward}\rangle/\epsilon$', ...
       'Interpreter', 'latex', 'FontSize', 14)

xlim([1, 1e4])
ylim([1e-4, 1e1])

set(gca, 'XScale', 'log', 'YScale', 'log')
set(gca, 'Box', 'on')
set(gca, 'TickDir', 'in')
set(gca, 'FontSize', 12)
set(gca, 'LineWidth', 1)
set(gca, 'XTick', 10.^(0:4))
set(gca, 'YTick', 10.^(-4:1))

% Values used by the two new curves:
disp(table(sigma_sharp_w2(:), r_eta_w2(:), flux_eps_w2(:), ...
    'VariableNames', {'sigma_sharp', 'r_eq_over_eta', 'flux_over_epsilon'}))
disp(table(sigma_sharp_alpha(:), r_eta_alpha(:), flux_eps_alpha(:), ...
    'VariableNames', {'sigma_sharp_alpha', 'r_eq_over_eta', 'flux_over_epsilon'}))
