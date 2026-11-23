"use client";

import Link from "next/link";
import { useEffect, useState, useTransition } from "react";
import { useIsAuthenticated } from "@/lib/auth-state";
import { getErrorMessage } from "@/lib/errors";
import {
  calculateGrossToNet,
  calculateNetToGross,
  CalculationBreakdownResponse,
  createUserEarning,
  deleteUserEarning,
  downloadEarningsExport,
  getFxRates,
  getToken,
  InverseQuoteResponse,
  listFeeTemplates,
  listUserEarnings,
} from "@/lib/api";

type TabKind = "calculator" | "inverse" | "earnings";

export default function FinancePage() {
  const [tab, setTab] = useState<TabKind>("calculator");
  const [isPending, startTransition] = useTransition();
  const [statusMsg, setStatusMsg] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  // Fee templates
  const [templates, setTemplates] = useState<Awaited<ReturnType<typeof listFeeTemplates>>["templates"]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("tpl_direct_stripe");

  // Gross-to-Net calculator state
  const [grossAmount, setGrossAmount] = useState<number>(800);
  const [baseCurrency, setBaseCurrency] = useState<string>("USD");
  const [targetCurrency, setTargetCurrency] = useState<string>("INR");
  const [feePct, setFeePct] = useState<number>(0.0);
  const [feeTaxPct, setFeeTaxPct] = useState<number>(0.0);
  const [withholdingPct, setWithholdingPct] = useState<number>(0.0);
  const [withdrawalFee, setWithdrawalFee] = useState<number>(0.0);
  const [withdrawalCount, setWithdrawalCount] = useState<number>(1);
  const [processorFeePct, setProcessorFeePct] = useState<number>(2.9);
  const [processorFeeFixed, setProcessorFeeFixed] = useState<number>(0.3);
  const [actualFxRate, setActualFxRate] = useState<number | undefined>(90.0);
  const [benchmarkFxRate, setBenchmarkFxRate] = useState<number | undefined>(90.0);
  const [reportedQuote, setReportedQuote] = useState<number | undefined>(undefined);

  // Gross-to-Net calculation result
  const [calcResult, setCalcResult] = useState<CalculationBreakdownResponse | null>(null);

  // Inverse Net-to-Gross quote state
  const [targetNet, setTargetNet] = useState<number>(900);
  const [hourlyHours, setHourlyHours] = useState<number>(20);
  const [inverseResult, setInverseResult] = useState<InverseQuoteResponse | null>(null);

  // Earnings Workspace state
  const [earningsData, setEarningsData] = useState<Awaited<ReturnType<typeof listUserEarnings>> | null>(null);
  const [newProjectTitle, setNewProjectTitle] = useState("");
  const [newClientName, setNewClientName] = useState("");
  const [newGross, setNewGross] = useState<number>(1000);
  const [newStatus, setNewStatus] = useState<"draft" | "invoiced" | "paid" | "cancelled">("paid");
  const isAuthed = useIsAuthenticated();

  useEffect(() => {
    const token = getToken();

    // Load templates
    listFeeTemplates()
      .then((res) => {
        setTemplates(res.templates || []);
      })
      .catch(() => {});

    // Initial calculation with default fixture ($800)
    runGrossCalculation();

    if (token) {
      loadEarnings();
    }
  }, []);

  const handleTemplateChange = (tplId: string) => {
    setSelectedTemplateId(tplId);
    const tpl = templates.find((t) => t.id === tplId);
    if (tpl) {
      setFeePct(tpl.contract_service_fee_pct ?? 0);
      setFeeTaxPct(tpl.fee_tax_pct ?? 0);
      setWithholdingPct(tpl.withholding_tax_pct ?? 0);
      setWithdrawalFee(tpl.withdrawal_fee ?? 0);
      setProcessorFeePct(tpl.processor_fee_pct ?? 0);
      setProcessorFeeFixed(tpl.processor_fee_fixed ?? 0);
      setBaseCurrency(tpl.currency || "USD");
    }
  };

  function runGrossCalculation() {
    startTransition(async () => {
      try {
        const res = await calculateGrossToNet({
          gross_amount: Number(grossAmount) || 0,
          currency: baseCurrency,
          target_currency: targetCurrency,
          contract_service_fee_pct: Number(feePct) || 0,
          fee_tax_pct: Number(feeTaxPct) || 0,
          withholding_tax_pct: Number(withholdingPct) || 0,
          withholding_tax_base: "gross",
          withdrawal_fee: Number(withdrawalFee) || 0,
          withdrawal_count: Number(withdrawalCount) || 1,
          processor_fee_pct: Number(processorFeePct) || 0,
          processor_fee_fixed: Number(processorFeeFixed) || 0,
          actual_fx_rate: actualFxRate ? Number(actualFxRate) : undefined,
          benchmark_fx_rate: benchmarkFxRate ? Number(benchmarkFxRate) : undefined,
          reported_bank_quote: reportedQuote ? Number(reportedQuote) : undefined,
        });
        setCalcResult(res);
        setStatusMsg(null);
      } catch (err: unknown) {
        setStatusMsg({ kind: "error", text: getErrorMessage(err, "") || "Failed to calculate" });
      }
    });
  }

  const runInverseCalculation = () => {
    startTransition(async () => {
      try {
        const res = await calculateNetToGross({
          target_net_amount: Number(targetNet) || 0,
          currency: baseCurrency,
          target_currency: undefined,
          hourly_hours: hourlyHours ? Number(hourlyHours) : undefined,
          contract_service_fee_pct: Number(feePct) || 0,
          fee_tax_pct: Number(feeTaxPct) || 0,
          withholding_tax_pct: Number(withholdingPct) || 0,
          withdrawal_fee: Number(withdrawalFee) || 0,
          processor_fee_pct: Number(processorFeePct) || 0,
          processor_fee_fixed: Number(processorFeeFixed) || 0,
          actual_fx_rate: undefined,
        });
        setInverseResult(res);
        setStatusMsg(null);
      } catch (err: unknown) {
        setStatusMsg({ kind: "error", text: getErrorMessage(err, "") || "Failed to calculate inverse quote" });
      }
    });
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      runGrossCalculation();
    }, 250);
    return () => clearTimeout(timer);
  }, [
    grossAmount,
    baseCurrency,
    targetCurrency,
    feePct,
    feeTaxPct,
    withholdingPct,
    withdrawalFee,
    withdrawalCount,
    processorFeePct,
    processorFeeFixed,
    actualFxRate,
    benchmarkFxRate,
    reportedQuote,
  ]);

  useEffect(() => {
    const timer = setTimeout(() => {
      runInverseCalculation();
    }, 250);
    return () => clearTimeout(timer);
  }, [
    targetNet,
    baseCurrency,
    hourlyHours,
    feePct,
    feeTaxPct,
    withholdingPct,
    withdrawalFee,
    processorFeePct,
    processorFeeFixed,
  ]);

  async function loadEarnings() {
    try {
      const data = await listUserEarnings();
      setEarningsData(data);
    } catch {
      // not authed or error
    }
  }

  const handleAddEarning = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProjectTitle.trim()) return;

    startTransition(async () => {
      try {
        await createUserEarning({
          project_title: newProjectTitle,
          client_name: newClientName || null,
          platform: selectedTemplateId.includes("fiverr") ? "fiverr" : "direct",
          currency: baseCurrency,
          gross_amount: Number(newGross) || 0,
          contract_service_fee: ((Number(newGross) || 0) * (Number(feePct) || 0)) / 100,
          invoice_status: newStatus,
          payment_date: newStatus === "paid" ? new Date().toISOString() : null,
        });
        setNewProjectTitle("");
        setNewClientName("");
        setStatusMsg({ kind: "success", text: "Won project recorded successfully." });
        await loadEarnings();
      } catch (err: unknown) {
        setStatusMsg({ kind: "error", text: getErrorMessage(err, "") || "Failed to record project" });
      }
    });
  };

  const handleDeleteEarning = async (id: string) => {
    startTransition(async () => {
      try {
        await deleteUserEarning(id);
        setStatusMsg({ kind: "success", text: "Record removed." });
        await loadEarnings();
      } catch (err: unknown) {
        setStatusMsg({ kind: "error", text: getErrorMessage(err, "") || "Failed to delete" });
      }
    });
  };

  const activeTemplate = templates.find((t) => t.id === selectedTemplateId);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      {/* Header */}
      <div className="mb-6 flex flex-col justify-between gap-4 border-b border-[var(--border)] pb-5 md:flex-row md:items-end">
        <div>
          <span className="text-xs font-semibold tracking-wider uppercase text-[var(--accent)]">
            Signal Desk — Financial Intelligence
          </span>
          <h1
            className="mt-1 text-2xl font-bold tracking-tight text-[var(--text)] md:text-3xl"
            style={{ fontFamily: "var(--font-display), Georgia, serif" }}
          >
            Transparent Earnings Calculator & Workspace
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-[var(--text-muted)]">
            Know what you actually receive in your bank account and what gross quote guarantees your desired take-home.
            Decimal precision, transparent fee breakdowns, and zero bank credentials.
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="flex rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-1">
          <button
            onClick={() => setTab("calculator")}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
              tab === "calculator"
                ? "bg-[var(--surface)] text-[var(--text)] shadow-sm"
                : "text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
          >
            Payout Calculator (Gross → Net)
          </button>
          <button
            onClick={() => {
              setTab("inverse");
              if (!inverseResult) runInverseCalculation();
            }}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
              tab === "inverse"
                ? "bg-[var(--surface)] text-[var(--text)] shadow-sm"
                : "text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
          >
            Quote Solver (Net → Gross)
          </button>
          <button
            onClick={() => {
              setTab("earnings");
              if (isAuthed) loadEarnings();
            }}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
              tab === "earnings"
                ? "bg-[var(--surface)] text-[var(--text)] shadow-sm"
                : "text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
          >
            Earnings Workspace
          </button>
        </div>
      </div>

      {/* Prominent Legal Disclaimer */}
      <div className="mb-6 rounded-md border border-amber-500/30 bg-amber-500/10 p-3.5 text-xs text-amber-800 dark:text-amber-200">
        <p className="font-semibold">Informational Purpose Only — No Fund Custody or Financial Advice</p>
        <p className="mt-0.5 opacity-90">
          This module calculates mathematical estimates based on user-entered values and publicly published platform policies.
          Signal Desk does not move funds, hold money, or store bank credentials. Taxes, withholding credits, and foreign exchange rates
          are subject to personal tax status and bank settlement variances.
        </p>
      </div>

      {/* Notifications banner */}
      {statusMsg && (
        <div
          className={`mb-6 rounded-md p-3 text-sm ${
            statusMsg.kind === "success"
              ? "border border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200"
              : "border border-rose-500/30 bg-rose-500/10 text-rose-800 dark:text-rose-200"
          }`}
        >
          {statusMsg.text}
        </div>
      )}

      {/* TAB 1: GROSS TO NET CALCULATOR */}
      {tab === "calculator" && (
        <div className="grid gap-6 lg:grid-cols-12">
          {/* Controls column */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 lg:col-span-5">
            <h2 className="text-base font-semibold text-[var(--text)]">Contract & Fee Parameters</h2>
            <p className="mt-0.5 text-xs text-[var(--text-muted)]">
              Select an official verified platform fee template or customize your deduction rates.
            </p>

            {/* Template Selector */}
            <div className="mt-4">
              <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Platform Fee Preset</label>
              <select
                className="sd-input mt-1 w-full"
                value={selectedTemplateId}
                onChange={(e) => handleTemplateChange(e.target.value)}
              >
                {templates.map((tpl) => (
                  <option key={tpl.id} value={tpl.id}>
                    {tpl.template_name} ({tpl.platform.toUpperCase()})
                  </option>
                ))}
              </select>
              {activeTemplate?.source_url && (
                <div className="mt-1 flex items-center justify-between text-[11px] text-[var(--text-muted)]">
                  <span>Effective: {activeTemplate.effective_date}</span>
                  <a
                    href={activeTemplate.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[var(--accent)] underline hover:opacity-80"
                  >
                    Verified Official Policy ↗
                  </a>
                </div>
              )}
            </div>

            {/* Gross Billed Amount */}
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Gross Billed Amount</label>
                <input
                  type="number"
                  min="0"
                  step="any"
                  className="sd-input mt-1 w-full text-base font-semibold"
                  value={grossAmount}
                  onChange={(e) => setGrossAmount(Number(e.target.value))}
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Billed Currency</label>
                <input
                  type="text"
                  className="sd-input mt-1 w-full uppercase"
                  value={baseCurrency}
                  onChange={(e) => setBaseCurrency(e.target.value.toUpperCase())}
                />
              </div>
            </div>

            {/* Platform Fee & Tax */}
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)]">Platform Fee (%)</label>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  className="sd-input mt-1 w-full"
                  value={feePct}
                  onChange={(e) => setFeePct(Number(e.target.value))}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)]">Tax on Fee / GST (%)</label>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  className="sd-input mt-1 w-full"
                  value={feeTaxPct}
                  onChange={(e) => setFeeTaxPct(Number(e.target.value))}
                />
              </div>
            </div>

            {/* Withholding & Withdrawal */}
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)]">
                  Withholding / TDS (%)
                  <span className="block text-[10px] text-emerald-600 dark:text-emerald-400">Recoverable credit</span>
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="sd-input mt-1 w-full"
                  value={withholdingPct}
                  onChange={(e) => setWithholdingPct(Number(e.target.value))}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)]">
                  Withdrawal Fee ({baseCurrency})
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="sd-input mt-1 w-full"
                  value={withdrawalFee}
                  onChange={(e) => setWithdrawalFee(Number(e.target.value))}
                />
              </div>
            </div>

            {/* FX Rates */}
            <div className="mt-4 rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-[var(--text)] uppercase">Foreign Currency Deposit</span>
                <input
                  type="text"
                  className="sd-input w-20 py-0.5 text-center text-xs font-semibold uppercase"
                  placeholder="Target"
                  value={targetCurrency}
                  onChange={(e) => setTargetCurrency(e.target.value.toUpperCase())}
                />
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-[var(--text-muted)]">Offered FX Rate</span>
                  <input
                    type="number"
                    step="0.0001"
                    className="sd-input mt-0.5 w-full text-xs"
                    value={actualFxRate ?? ""}
                    onChange={(e) => setActualFxRate(e.target.value ? Number(e.target.value) : undefined)}
                  />
                </div>
                <div>
                  <span className="text-[var(--text-muted)]">Benchmark (Mid-market)</span>
                  <input
                    type="number"
                    step="0.0001"
                    className="sd-input mt-0.5 w-full text-xs"
                    value={benchmarkFxRate ?? ""}
                    onChange={(e) => setBenchmarkFxRate(e.target.value ? Number(e.target.value) : undefined)}
                  />
                </div>
              </div>
              <div className="mt-2">
                <span className="text-[11px] text-[var(--text-muted)]">Bank Quote for Reconciliation (optional)</span>
                <input
                  type="number"
                  step="0.01"
                  className="sd-input mt-0.5 w-full text-xs"
                  placeholder="e.g. 64403.44"
                  value={reportedQuote ?? ""}
                  onChange={(e) => setReportedQuote(e.target.value ? Number(e.target.value) : undefined)}
                />
              </div>
            </div>

            {/* Action button */}
            <button
              onClick={runGrossCalculation}
              disabled={isPending}
              className="mt-5 w-full rounded-md bg-[var(--accent)] py-2 text-sm font-semibold text-white shadow-sm transition hover:opacity-95 disabled:opacity-50"
            >
              {isPending ? "Calculating..." : "Calculate Take-Home Breakdown"}
            </button>
          </div>

          {/* Results column */}
          <div className="space-y-4 lg:col-span-7">
            {calcResult && (
              <>
                {/* Summary Cards */}
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
                    <span className="text-xs font-medium text-[var(--text-muted)] uppercase">Bank Deposit</span>
                    <div className="mt-1 text-2xl font-bold text-[var(--text)]">
                      {calcResult.calculation.target_currency !== calcResult.calculation.currency
                        ? `${calcResult.calculation.bank_deposit_amount.toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })} ${calcResult.calculation.target_currency}`
                        : `$${calcResult.calculation.bank_deposit_amount.toFixed(2)}`}
                    </div>
                    {calcResult.calculation.target_currency !== calcResult.calculation.currency && (
                      <span className="mt-0.5 block text-xs text-[var(--text-muted)]">
                        (${calcResult.calculation.net_payout_amount.toFixed(2)} {calcResult.calculation.currency})
                      </span>
                    )}
                  </div>

                  <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-4 shadow-sm">
                    <span className="text-xs font-medium text-rose-700 dark:text-rose-300 uppercase">
                      Permanent Cost
                    </span>
                    <div className="mt-1 text-2xl font-bold text-rose-600 dark:text-rose-400">
                      ${calcResult.calculation.permanent_costs.toFixed(2)}
                    </div>
                    <span className="mt-0.5 block text-xs text-rose-600/80 dark:text-rose-400/80">
                      {calcResult.calculation.effective_total_cost_pct.toFixed(1)}% of gross revenue
                    </span>
                  </div>

                  <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 shadow-sm">
                    <span className="text-xs font-medium text-emerald-700 dark:text-emerald-300 uppercase">
                      Recoverable Tax Credit
                    </span>
                    <div className="mt-1 text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                      ${calcResult.calculation.recoverable_credits.toFixed(2)}
                    </div>
                    <span className="mt-0.5 block text-xs text-emerald-600/80 dark:text-emerald-400/80">
                      Claimable on tax return (TDS)
                    </span>
                  </div>
                </div>

                {/* FX Spread Analysis & Bank Reconciliation */}
                {calcResult.calculation.target_currency !== calcResult.calculation.currency && (
                  <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
                    <h3 className="text-sm font-semibold text-[var(--text)]">FX Rate Transparency & Spread Cost</h3>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2 text-xs">
                      <div>
                        <span className="text-[var(--text-muted)]">Benchmark Rate (Mid-market):</span>
                        <p className="font-semibold text-[var(--text)]">
                          1 {calcResult.calculation.currency} = {benchmarkFxRate || "—"} {calcResult.calculation.target_currency}
                        </p>
                      </div>
                      <div>
                        <span className="text-[var(--text-muted)]">Platform Offered Rate:</span>
                        <p className="font-semibold text-[var(--text)]">
                          1 {calcResult.calculation.currency} = {actualFxRate || "—"} {calcResult.calculation.target_currency}
                        </p>
                      </div>
                    </div>
                    {calcResult.calculation.fx_spread_cost_total != null && (
                      <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
                        Estimated hidden FX spread drag: ~{calcResult.calculation.fx_spread_cost_total.toFixed(2)}{" "}
                        {calcResult.calculation.target_currency}
                      </p>
                    )}
                    {reportedQuote != null && calcResult.calculation.reconciliation_status && (
                      <div className="mt-3 rounded border border-[var(--border)] bg-[var(--surface-sunken)] p-2 text-xs">
                        <span className="font-medium">Bank Quote Reconciliation:</span>{" "}
                        {calcResult.calculation.reconciliation_status === "reconciled_exact" ? (
                          <span className="text-emerald-600 dark:text-emerald-400 font-semibold">Exact match (0.00 discrepancy)</span>
                        ) : calcResult.calculation.reconciliation_status === "reconciled_within_tolerance" ? (
                          <span className="text-blue-600 dark:text-blue-400 font-semibold">
                            Reconciled within tolerance ({calcResult.calculation.reconciliation_discrepancy} discrepancy)
                          </span>
                        ) : (
                          <span className="text-rose-600 font-semibold">Discrepancy exceeds tolerance threshold</span>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Itemized Deduction Waterfall */}
                <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)]">
                  <div className="border-b border-[var(--border)] px-4 py-3">
                    <h3 className="text-sm font-semibold text-[var(--text)]">Itemized Deduction Waterfall</h3>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="border-b border-[var(--border)] bg-[var(--surface-sunken)] text-[var(--text-muted)] uppercase">
                        <tr>
                          <th className="px-4 py-2.5">Item</th>
                          <th className="px-4 py-2.5">Type</th>
                          <th className="px-4 py-2.5 text-right">Amount ({calcResult.calculation.currency})</th>
                          <th className="px-4 py-2.5 text-right">% Gross</th>
                          <th className="px-4 py-2.5">Explanation</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border)]">
                        <tr className="bg-[var(--surface-sunken)]/40 font-semibold">
                          <td className="px-4 py-2.5">Gross Billed</td>
                          <td className="px-4 py-2.5 text-[var(--text-muted)]">—</td>
                          <td className="px-4 py-2.5 text-right">
                            ${calcResult.calculation.gross_amount.toFixed(2)}
                          </td>
                          <td className="px-4 py-2.5 text-right">100.0%</td>
                          <td className="px-4 py-2.5 text-[var(--text-muted)]">Agreed contract price</td>
                        </tr>
                        {calcResult.calculation.itemized_deductions.map((item, idx) => (
                          <tr key={idx} className="hover:bg-[var(--surface-sunken)]/20">
                            <td className="px-4 py-2 font-medium text-[var(--text)]">{item.name}</td>
                            <td className="px-4 py-2">
                              {item.category === "permanent_cost" ? (
                                <span className="rounded bg-rose-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-rose-600 dark:text-rose-400">
                                  Permanent Cost
                                </span>
                              ) : item.category === "recoverable_credit" ? (
                                <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                                  Tax Credit
                                </span>
                              ) : (
                                <span className="rounded bg-blue-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-blue-600 dark:text-blue-400">
                                  Payout
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-2 text-right font-medium">
                              ${item.amount_base.toFixed(2)}
                            </td>
                            <td className="px-4 py-2 text-right text-[var(--text-muted)]">
                              {item.pct_of_gross.toFixed(2)}%
                            </td>
                            <td className="px-4 py-2 text-[var(--text-muted)]">{item.notes}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: INVERSE NET TO GROSS QUOTE SOLVER */}
      {tab === "inverse" && (
        <div className="grid gap-6 lg:grid-cols-12">
          {/* Input controls */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 lg:col-span-5">
            <h2 className="text-base font-semibold text-[var(--text)]">Target Net-to-Gross Solver</h2>
            <p className="mt-0.5 text-xs text-[var(--text-muted)]">
              Specify how much you want in your bank account, and our exact algebra solves what you must quote.
            </p>

            <div className="mt-4">
              <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Platform Preset</label>
              <select
                className="sd-input mt-1 w-full"
                value={selectedTemplateId}
                onChange={(e) => handleTemplateChange(e.target.value)}
              >
                {templates.map((tpl) => (
                  <option key={tpl.id} value={tpl.id}>
                    {tpl.template_name}
                  </option>
                ))}
              </select>
            </div>

            <div className="mt-4">
              <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">
                Desired Net Bank Deposit ({baseCurrency})
              </label>
              <input
                type="number"
                min="1"
                step="any"
                className="sd-input mt-1 w-full text-lg font-bold"
                value={targetNet}
                onChange={(e) => setTargetNet(Number(e.target.value))}
              />
            </div>

            <div className="mt-4">
              <label className="text-xs font-medium text-[var(--text-muted)]">
                Project Hours (for hourly quote suggestion)
              </label>
              <input
                type="number"
                min="1"
                className="sd-input mt-1 w-full"
                value={hourlyHours}
                onChange={(e) => setHourlyHours(Number(e.target.value))}
              />
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)]">Platform Fee (%)</label>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  className="sd-input mt-1 w-full"
                  value={feePct}
                  onChange={(e) => setFeePct(Number(e.target.value))}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)]">Tax on Fee (%)</label>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  className="sd-input mt-1 w-full"
                  value={feeTaxPct}
                  onChange={(e) => setFeeTaxPct(Number(e.target.value))}
                />
              </div>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)]">Withholding / TDS (%)</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="sd-input mt-1 w-full"
                  value={withholdingPct}
                  onChange={(e) => setWithholdingPct(Number(e.target.value))}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)]">Withdrawal Fee ({baseCurrency})</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="sd-input mt-1 w-full"
                  value={withdrawalFee}
                  onChange={(e) => setWithdrawalFee(Number(e.target.value))}
                />
              </div>
            </div>

            <button
              onClick={runInverseCalculation}
              disabled={isPending}
              className="mt-5 w-full rounded-md bg-[var(--accent)] py-2 text-sm font-semibold text-white shadow-sm transition hover:opacity-95 disabled:opacity-50"
            >
              {isPending ? "Solving Quote..." : "Solve Required Gross Quote"}
            </button>
          </div>

          {/* Results display */}
          <div className="space-y-4 lg:col-span-7">
            {inverseResult && (
              <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
                <div className="flex items-center justify-between border-b border-[var(--border)] pb-4">
                  <div>
                    <span className="text-xs font-semibold tracking-wider uppercase text-[var(--accent)]">
                      Exact Inverse Quote Solution
                    </span>
                    <h3 className="text-xl font-bold text-[var(--text)]">
                      Required Gross Quote: ${inverseResult.quote.required_gross_amount.toFixed(2)}{" "}
                      {inverseResult.quote.currency}
                    </h3>
                  </div>
                  {inverseResult.quote.meets_target ? (
                    <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                      Verified Round-Trip Exact
                    </span>
                  ) : (
                    <span className="rounded-full bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-600 dark:text-amber-400">
                      Diff: ${inverseResult.quote.rounding_discrepancy.toFixed(2)}
                    </span>
                  )}
                </div>

                {inverseResult.quote.suggested_hourly_rate && (
                  <div className="mt-4 rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-3">
                    <span className="text-xs font-medium text-[var(--text-muted)]">Hourly Rate Suggestion</span>
                    <div className="mt-1 text-xl font-bold text-[var(--text)]">
                      ${inverseResult.quote.suggested_hourly_rate.toFixed(2)} / hr
                    </div>
                    <span className="text-[11px] text-[var(--text-muted)]">
                      Across {inverseResult.quote.hourly_hours} estimated project hours
                    </span>
                  </div>
                )}

                <div className="mt-5 space-y-2 text-xs">
                  <h4 className="font-semibold text-[var(--text)]">Reconciliation Proof</h4>
                  <div className="flex justify-between border-b border-[var(--border)] py-1.5">
                    <span className="text-[var(--text-muted)]">Target Net Desired:</span>
                    <span className="font-semibold">${inverseResult.quote.target_net_amount.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between border-b border-[var(--border)] py-1.5">
                    <span className="text-[var(--text-muted)]">Platform Fee Deducted:</span>
                    <span className="text-rose-600 dark:text-rose-400">
                      -${inverseResult.quote.deduction_breakdown.contract_service_fee.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between border-b border-[var(--border)] py-1.5">
                    <span className="text-[var(--text-muted)]">Tax on Platform Fee:</span>
                    <span className="text-rose-600 dark:text-rose-400">
                      -${inverseResult.quote.deduction_breakdown.fee_tax.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between border-b border-[var(--border)] py-1.5">
                    <span className="text-[var(--text-muted)]">Withholding Tax (Advance Credit):</span>
                    <span className="text-emerald-600 dark:text-emerald-400">
                      -${inverseResult.quote.deduction_breakdown.withholding_tax.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between border-b border-[var(--border)] py-1.5">
                    <span className="text-[var(--text-muted)]">Withdrawal & Processor Fees:</span>
                    <span className="text-rose-600 dark:text-rose-400">
                      -$
                      {(
                        inverseResult.quote.deduction_breakdown.withdrawal_fee_total +
                        inverseResult.quote.deduction_breakdown.processor_fee_total
                      ).toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between pt-2 text-sm font-bold">
                    <span>Final Verified Deposit:</span>
                    <span className="text-emerald-600 dark:text-emerald-400">
                      ${inverseResult.quote.verification_net_deposit.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: WON PROJECTS & EARNINGS WORKSPACE */}
      {tab === "earnings" && (
        <div className="space-y-6">
          {/* Auth check */}
          {!isAuthed ? (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-8 text-center">
              <h3 className="text-lg font-semibold text-[var(--text)]">Sign In to Save Confirmed Earnings</h3>
              <p className="mt-1 text-sm text-[var(--text-muted)]">
                The public calculator works without signing in. To track won projects, separate pipeline from realized cash,
                and export CSV ledgers, sign in to your account.
              </p>
              <Link
                href="/auth"
                className="mt-4 inline-block rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white shadow-sm"
              >
                Sign In to Account
              </Link>
            </div>
          ) : (
            <>
              {/* Metrics Bar */}
              {earningsData?.summary && (
                <div className="grid gap-4 sm:grid-cols-4">
                  <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
                    <span className="text-xs font-medium text-[var(--text-muted)] uppercase">Realized Cash Received</span>
                    <div className="mt-1 text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                      ${earningsData.summary.cash_received.toFixed(2)}
                    </div>
                    <span className="text-[11px] text-[var(--text-muted)]">Only paid invoices</span>
                  </div>

                  <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
                    <span className="text-xs font-medium text-[var(--text-muted)] uppercase">Unrealized Pipeline</span>
                    <div className="mt-1 text-2xl font-bold text-blue-600 dark:text-blue-400">
                      ${earningsData.summary.pipeline_estimated_gross.toFixed(2)}
                    </div>
                    <span className="text-[11px] text-[var(--text-muted)]">Draft & Invoiced (strictly separated)</span>
                  </div>

                  <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
                    <span className="text-xs font-medium text-[var(--text-muted)] uppercase">Effective Take-Home</span>
                    <div className="mt-1 text-2xl font-bold text-[var(--text)]">
                      {earningsData.summary.effective_take_home_rate_pct.toFixed(1)}%
                    </div>
                    <span className="text-[11px] text-[var(--text-muted)]">Cash vs Gross</span>
                  </div>

                  <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
                    <span className="text-xs font-medium text-[var(--text-muted)] uppercase">Platform Fees Paid</span>
                    <div className="mt-1 text-2xl font-bold text-rose-600 dark:text-rose-400">
                      ${earningsData.summary.platform_fees_paid.toFixed(2)}
                    </div>
                    <span className="text-[11px] text-[var(--text-muted)]">Permanent platform deductions</span>
                  </div>
                </div>
              )}

              {/* Record Project Form */}
              <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
                <h3 className="text-base font-semibold text-[var(--text)]">Record Won Project / Invoice</h3>
                <p className="mt-0.5 text-xs text-[var(--text-muted)]">
                  Add user-confirmed projects. Zero sensitive bank credentials or account numbers are collected or stored.
                </p>
                <form onSubmit={handleAddEarning} className="mt-4 grid gap-3 sm:grid-cols-5">
                  <div className="sm:col-span-2">
                    <input
                      type="text"
                      required
                      placeholder="Project Title (e.g. Next.js SaaS MVP)"
                      className="sd-input w-full text-xs"
                      value={newProjectTitle}
                      onChange={(e) => setNewProjectTitle(e.target.value)}
                    />
                  </div>
                  <div>
                    <input
                      type="text"
                      placeholder="Client Name (optional)"
                      className="sd-input w-full text-xs"
                      value={newClientName}
                      onChange={(e) => setNewClientName(e.target.value)}
                    />
                  </div>
                  <div>
                    <input
                      type="number"
                      required
                      min="0"
                      step="any"
                      placeholder="Gross Amount ($)"
                      className="sd-input w-full text-xs font-medium"
                      value={newGross}
                      onChange={(e) => setNewGross(Number(e.target.value))}
                    />
                  </div>
                  <div className="flex gap-2">
                    <select
                      className="sd-input w-full text-xs"
                      value={newStatus}
                      onChange={(e) => setNewStatus(e.target.value as typeof newStatus)}
                    >
                      <option value="paid">Paid (Cash)</option>
                      <option value="invoiced">Invoiced (Pending)</option>
                      <option value="draft">Draft Proposal</option>
                    </select>
                    <button
                      type="submit"
                      disabled={isPending}
                      className="rounded-md bg-[var(--accent)] px-3 text-xs font-semibold text-white transition hover:opacity-95"
                    >
                      Add
                    </button>
                  </div>
                </form>
              </div>

              {/* Projects Table & Export */}
              <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)]">
                <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
                  <h3 className="text-sm font-semibold text-[var(--text)]">Confirmed Project Ledger</h3>
                  <button
                    type="button"
                    onClick={() => void downloadEarningsExport().catch((error: unknown) => {
                      setStatusMsg({ kind: "error", text: getErrorMessage(error, "Could not download the ledger.") });
                    })}
                    className="rounded border border-[var(--border)] bg-[var(--surface-sunken)] px-2.5 py-1 text-xs font-medium text-[var(--text)] hover:bg-[var(--border)]"
                  >
                    Download CSV
                  </button>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-[var(--border)] bg-[var(--surface-sunken)] text-[var(--text-muted)] uppercase">
                      <tr>
                        <th className="px-4 py-2.5">Project</th>
                        <th className="px-4 py-2.5">Client</th>
                        <th className="px-4 py-2.5">Status</th>
                        <th className="px-4 py-2.5 text-right">Gross</th>
                        <th className="px-4 py-2.5 text-right">Platform Fee</th>
                        <th className="px-4 py-2.5 text-right">Net Received</th>
                        <th className="px-4 py-2.5 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border)]">
                      {earningsData?.earnings?.length ? (
                        earningsData.earnings.map((earn) => (
                          <tr key={earn.id} className="hover:bg-[var(--surface-sunken)]/20">
                            <td className="px-4 py-2.5 font-medium text-[var(--text)]">{earn.project_title}</td>
                            <td className="px-4 py-2.5 text-[var(--text-muted)]">{earn.client_name || "—"}</td>
                            <td className="px-4 py-2.5">
                              <span
                                className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                                  earn.invoice_status === "paid"
                                    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                                    : earn.invoice_status === "invoiced"
                                    ? "bg-blue-500/10 text-blue-600 dark:text-blue-400"
                                    : "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                                }`}
                              >
                                {earn.invoice_status.toUpperCase()}
                              </span>
                            </td>
                            <td className="px-4 py-2.5 text-right font-medium">
                              ${earn.gross_amount.toFixed(2)}
                            </td>
                            <td className="px-4 py-2.5 text-right text-rose-600 dark:text-rose-400">
                              -${earn.contract_service_fee.toFixed(2)}
                            </td>
                            <td className="px-4 py-2.5 text-right font-bold text-emerald-600 dark:text-emerald-400">
                              ${earn.net_received_in_bank.toFixed(2)}
                            </td>
                            <td className="px-4 py-2.5 text-right">
                              <button
                                onClick={() => handleDeleteEarning(earn.id)}
                                className="text-rose-500 hover:underline"
                              >
                                Delete
                              </button>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={7} className="px-4 py-6 text-center text-xs text-[var(--text-muted)]">
                            No projects recorded yet. Use the form above to record won opportunities.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
