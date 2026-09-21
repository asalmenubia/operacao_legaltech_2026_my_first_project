(() => {
  const data = window.LEGALTECH_DATA;
  if (!data || !window.Plotly) return;
  const $ = id => document.getElementById(id);
  const colors = { navy: '#123b52', teal: '#16847a', gold: '#d69b31', red: '#ba4a45', gray: '#81909b' };
  const layout = title => ({ title: { text: title, x: .03, font: { family: 'Georgia, serif', size: 20 } }, paper_bgcolor: '#fffefa', plot_bgcolor: '#fffefa', margin: { l: 55, r: 25, t: 60, b: 55 }, font: { family: 'Inter, system-ui, sans-serif', color: '#17212b' }, legend: { orientation: 'h', y: 1.12 } });
  const config = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d'] };
  const month = value => value ? String(value).slice(0, 7) : '';
  const label = value => String(value || 'Unassigned').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
  const money = value => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(value || 0);
  const total = (rows, field) => rows.reduce((sum, row) => sum + Number(row[field] || 0), 0);
  const counts = (rows, field) => rows.reduce((acc, row) => { const key = label(row[field]); acc[key] = (acc[key] || 0) + 1; return acc; }, {});
  const values = (rows, field) => [...new Set(rows.map(row => row[field]).filter(Boolean))].sort();

  const filters = {
    month: $('month-filter'), channel: $('channel-filter'), type: $('type-filter'),
    stage: $('stage-filter'), outcome: $('outcome-filter'), lawyer: $('lawyer-filter')
  };
  const allMonths = [...new Set([
    ...data.matters.map(r => month(r.opened_at)), ...data.invoices.map(r => month(r.issued_at)),
    ...data.inquiries.map(r => month(r.month)), ...data.consultations.map(r => month(r.month))
  ].filter(Boolean))].sort();
  const fill = (select, items) => items.forEach(value => select.add(new Option(label(value), value)));
  fill(filters.month, allMonths); fill(filters.channel, values(data.inquiries, 'origin_channel'));
  fill(filters.type, values(data.matters, 'matter_type')); fill(filters.stage, values(data.matters, 'current_stage'));
  fill(filters.outcome, values(data.matters, 'outcome')); fill(filters.lawyer, values(data.matters, 'responsible_lawyer'));

  $('validation').textContent = `${label(data.metadata.validation_status)} · ${data.metadata.critical_findings} critical findings`;
  $('generated-at').textContent = `Snapshot generated ${new Date(data.metadata.generated_at).toLocaleString()}`;

  function render() {
    const selectedMonth = filters.month.value;
    const matters = data.matters.filter(r => (!selectedMonth || month(r.opened_at) === selectedMonth) && (!filters.type.value || r.matter_type === filters.type.value) && (!filters.stage.value || r.current_stage === filters.stage.value) && (!filters.outcome.value || r.outcome === filters.outcome.value) && (!filters.lawyer.value || r.responsible_lawyer === filters.lawyer.value));
    const invoices = data.invoices.filter(r => !selectedMonth || month(r.issued_at) === selectedMonth);
    const inquiries = data.inquiries.filter(r => (!selectedMonth || month(r.month) === selectedMonth) && (!filters.channel.value || r.origin_channel === filters.channel.value));
    const consultations = data.consultations.filter(r => !selectedMonth || month(r.month) === selectedMonth);

    $('kpi-matters').textContent = matters.length.toLocaleString();
    $('kpi-active').textContent = matters.filter(r => r.current_stage !== 'closed').length.toLocaleString();
    $('kpi-invoiced').textContent = money(total(invoices, 'invoiced_amount'));
    $('kpi-paid').textContent = money(total(invoices, 'paid_amount'));
    $('kpi-outstanding').textContent = money(total(invoices, 'outstanding_amount'));
    $('kpi-overdue').textContent = invoices.filter(r => r.calculated_status === 'overdue').length.toLocaleString();

    const stages = counts(matters, 'current_stage');
    Plotly.react('matters-stage-chart', [{ type: 'bar', x: Object.keys(stages), y: Object.values(stages), marker: { color: colors.teal } }], layout('Matters by current stage'), config);
    const types = counts(matters, 'matter_type');
    Plotly.react('matter-type-chart', [{ type: 'pie', labels: Object.keys(types), values: Object.values(types), hole: .55, marker: { colors: [colors.navy, colors.teal, colors.gold, colors.red, colors.gray] } }], layout('Matter mix'), config);
    const missing = matters.filter(r => Number(r.missing_document_count) > 0).sort((a, b) => b.missing_document_count - a.missing_document_count).slice(0, 12);
    Plotly.react('missing-docs-chart', [{ type: 'bar', orientation: 'h', y: missing.map(r => `Matter ${r.matter_id}`).reverse(), x: missing.map(r => r.missing_document_count).reverse(), marker: { color: colors.red } }], layout('Largest missing-document queues'), config);

    Plotly.react('inquiry-chart', [
      { type: 'bar', name: 'Inquiries', x: inquiries.map(r => r.month), y: inquiries.map(r => r.inquiry_count), marker: { color: colors.navy } },
      { type: 'scatter', mode: 'lines+markers', name: 'Avg response minutes', x: inquiries.map(r => r.month), y: inquiries.map(r => r.average_response_minutes), yaxis: 'y2', line: { color: colors.gold } }
    ], { ...layout('Inquiry demand and response time'), yaxis2: { overlaying: 'y', side: 'right', title: 'Minutes', showgrid: false }, barmode: 'stack' }, config);
    const funnelLabels = ['Scheduled', 'Held', 'Accepted', 'Paid'];
    const funnelValues = ['scheduled_count', 'held_count', 'accepted_count', 'paid_count'].map(field => total(consultations, field));
    Plotly.react('funnel-chart', [{ type: 'funnel', y: funnelLabels, x: funnelValues, marker: { color: [colors.navy, colors.teal, colors.gold, colors.red] } }], layout('Consultation funnel'), config);

    const monthly = {};
    invoices.forEach(r => { const key = month(r.issued_at); monthly[key] ||= { invoiced: 0, paid: 0, outstanding: 0 }; monthly[key].invoiced += Number(r.invoiced_amount); monthly[key].paid += Number(r.paid_amount); monthly[key].outstanding += Number(r.outstanding_amount); });
    const months = Object.keys(monthly).sort();
    Plotly.react('finance-chart', [
      { type: 'bar', name: 'Invoiced', x: months, y: months.map(m => monthly[m].invoiced), marker: { color: colors.navy } },
      { type: 'bar', name: 'Paid', x: months, y: months.map(m => monthly[m].paid), marker: { color: colors.teal } },
      { type: 'bar', name: 'Outstanding', x: months, y: months.map(m => monthly[m].outstanding), marker: { color: colors.red } }
    ], { ...layout('Monthly financial position'), barmode: 'group', yaxis: { tickprefix: '€', separatethousands: true } }, config);
    const statuses = counts(invoices, 'calculated_status');
    Plotly.react('invoice-status-chart', [{ type: 'bar', x: Object.keys(statuses), y: Object.values(statuses), marker: { color: Object.keys(statuses).map(s => s === 'Overdue' ? colors.red : colors.teal) } }], layout('Invoice balance status'), config);
  }

  Object.values(filters).forEach(select => select.addEventListener('change', render));
  $('reset-filters').addEventListener('click', () => { Object.values(filters).forEach(select => { select.value = ''; }); render(); });
  render();
})();
