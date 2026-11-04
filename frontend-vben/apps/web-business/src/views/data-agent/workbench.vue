<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { Alert, Button, Card, Collapse, CollapsePanel, Input, Select, Space, Statistic, Table, Tag, Timeline, TimelineItem } from 'ant-design-vue';
import { Page } from '@vben/common-ui';
import { api, session } from './client';
import { approveQuestion, askQuestion, getExamples, getSystemStatus } from './api';
import type { QuestionRecord } from './types';
import ResultChart from './result-chart.vue';

const route = useRoute();
const notice = ref('');
const examples = ref<string[]>([]);
const question = ref('今年每个月的已支付销售额是多少？');
const record = ref<QuestionRecord | null>(null);
const loading = ref(false);
const error = ref('');
const connected = ref(false);
const database = ref('data_agent_demo');
const view = ref<'chart' | 'table'>('chart');

watch(() => route.query.question, value => { if (value) question.value = String(value); });
const columns = computed(() => record.value?.result?.columns.map(key => ({ title: key, dataIndex: key, key })) ?? []);
const resultRows = computed(() => record.value?.result?.rows ?? []);
const numericField = computed(() => {
  const result = record.value?.result;
  if (!result) return null;
  return result.columns.find((column) => result.rows.some((row) => Number.isFinite(Number(row[column])))) ?? null;
});
const totalValue = computed(() => numericField.value ? resultRows.value.reduce((sum, row) => sum + (Number(row[numericField.value!]) || 0), 0) : 0);
const peakRow = computed(() => {
  if (!numericField.value) return null;
  return resultRows.value.reduce((peak, row) => (Number(row[numericField.value!]) > Number(peak?.[numericField.value!]) ? row : peak), resultRows.value[0]);
});
const lowestRow = computed(() => {
  if (!numericField.value) return null;
  return resultRows.value.reduce((lowest, row) => (Number(row[numericField.value!]) < Number(lowest?.[numericField.value!]) ? row : lowest), resultRows.value[0]);
});
const formatDate = (value?: string) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—';

async function favorite() {
  try { await api('/favorites', { method: 'POST', body: JSON.stringify({ title: question.value.slice(0, 100), question: question.value }) }); notice.value = '已保存到收藏查询'; }
  catch (e) { error.value = String(e); }
}
async function submit() {
  notice.value = '';
  if (session.user?.role === 'viewer' || loading.value || question.value.trim().length < 2) return;
  loading.value = true; error.value = ''; record.value = null;
  try { record.value = await askQuestion(question.value.trim()); }
  catch (e) { error.value = e instanceof Error ? e.message : '查询失败'; }
  finally { loading.value = false; }
}
async function approve() {
  if (!record.value || loading.value) return;
  loading.value = true; error.value = '';
  try { record.value = await approveQuestion(record.value); }
  catch (e) { error.value = e instanceof Error ? e.message : '审批失败'; }
  finally { loading.value = false; }
}
onMounted(async () => {
  try {
    const [health, items] = await Promise.all([getSystemStatus(), getExamples()]);
    connected.value = health.database.connected; database.value = health.database.name ?? 'data_agent_demo'; examples.value = items;
    if (route.query.question) question.value = String(route.query.question);
  } catch (e) { error.value = e instanceof Error ? e.message : '服务连接失败'; }
});
</script>

<template>
  <Page title="查询工作台" description="用自然语言查询业务数据，快速获得可解释的结果">
    <div class="workbench">
      <Card class="query-card" :bordered="false">
        <div class="query-card__top"><div><div class="eyebrow">QUERYX · DATA WORKBENCH</div><h1>让数据回答业务问题</h1><p>输入一个清晰的问题，系统会生成查询、校验口径并返回可视化结果。</p></div><Tag :color="connected ? 'success' : 'error'" class="status-tag">{{ connected ? '数据库已连接' : '数据库未连接' }}</Tag></div>
        <label for="business-question" class="field-label">业务问题</label>
        <Input.TextArea id="business-question" v-model:value="question" :rows="3" :maxlength="2000" placeholder="例如：今年每个月的已支付销售额是多少？" @keydown.ctrl.enter.prevent="submit" />
        <div class="query-card__footer"><Space wrap><span class="muted">常用查询</span><Select aria-label="常用查询" placeholder="选择一个示例问题" :value="undefined" style="width: 300px; max-width: 100%" :options="examples.map(value => ({ value, label: value }))" @change="(value) => question = String(value)" /></Space><Button type="primary" size="large" :loading="loading" :disabled="question.trim().length < 2 || session.user?.role === 'viewer'" @click="submit">执行查询 <span class="shortcut">Ctrl + Enter</span></Button></div>
        <div class="source-line"><span class="source-dot"></span>数据源：MySQL / {{ database }} <span>·</span> 演示数据 · 只读访问</div>
      </Card>
      <Alert v-if="notice" :message="notice" type="success" show-icon /><Alert v-if="error" :message="error" type="error" show-icon />
      <Card v-if="record?.status === 'approval_required'" class="approval-card" :bordered="false" title="查询需要审批"><p v-for="reason in record.risk?.reasons" :key="reason">{{ reason }}</p><Button type="primary" :loading="loading" @click="approve">确认执行</Button></Card>
      <template v-if="record?.result">
        <div class="result-heading"><div><div class="eyebrow">QUERY RESULT</div><h2>查询结果</h2><p>{{ record.answer || '已完成查询，以下是本次结果。' }}</p></div><Space wrap><Button @click="favorite">收藏查询</Button><Button :href="`/api/v1/questions/${record.id}/export`">导出 Excel</Button></Space></div>
        <div class="metric-grid"><Card :bordered="false" class="metric-card metric-card--primary"><div class="metric-label">累计值</div><Statistic :value="totalValue" :precision="2" prefix="¥" /><div class="metric-note">基于本次返回结果汇总</div></Card><Card :bordered="false" class="metric-card"><div class="metric-label">数据行数</div><Statistic :value="record.result.row_count" suffix="行" /><div class="metric-note">查询耗时 {{ record.result.elapsed_ms }} ms</div></Card><Card :bordered="false" class="metric-card"><div class="metric-label">最高值</div><Statistic :value="Number(peakRow?.[numericField!] || 0)" :precision="2" prefix="¥" /><div class="metric-note">{{ peakRow ? String(peakRow[record.result.columns[0]!]) : '—' }}</div></Card><Card :bordered="false" class="metric-card"><div class="metric-label">最低值</div><Statistic :value="Number(lowestRow?.[numericField!] || 0)" :precision="2" prefix="¥" /><div class="metric-note">{{ lowestRow ? String(lowestRow[record.result.columns[0]!]) : '—' }}</div></Card></div>
        <div class="result-grid"><Card :bordered="false" class="chart-card"><template #title><div class="card-title"><strong>趋势概览</strong><span>按查询结果自动生成</span></div></template><template #extra><Select v-model:value="view" :options="[{ value: 'chart', label: '图表视图' }, { value: 'table', label: '数据表格' }]" style="width: 118px" /></template><ResultChart v-if="view === 'chart' && record.chart && record.chart.type !== 'table'" :key="record.id" :result="record.result" :chart="record.chart" :height="330" /><Table v-else :columns="columns" :data-source="record.result.rows.map((row, index) => ({ ...row, _key: index }))" row-key="_key" size="small" :pagination="{ pageSize: 10, showSizeChanger: true }" :scroll="{ x: 'max-content' }" /></Card><Card :bordered="false" class="detail-card" title="结果说明"><div class="detail-item"><span>业务问题</span><strong>{{ record.question }}</strong></div><div class="detail-item"><span>统计口径</span><strong>{{ record.generated?.assumptions?.join('；') || '已支付订单的订单实付金额' }}</strong></div><div class="detail-item"><span>导出时间</span><strong>{{ formatDate(record.created_at) }}</strong></div><div class="detail-item"><span>执行账号</span><strong>{{ record.requested_by || '当前用户' }}</strong></div><div class="detail-item"><span>数据状态</span><Tag color="success">已完成</Tag></div></Card></div>
        <Alert v-if="record.result.truncated" class="result-alert" message="结果已达到返回上限，请缩小查询范围。" type="warning" show-icon />
      </template>
      <Card v-else-if="!loading" class="empty-card" :bordered="false"><div class="empty-icon">⌁</div><h3>准备好开始查询</h3><p>输入业务问题后，结果会以指标、趋势图和明细表的形式呈现。</p></Card><Card v-else class="empty-card" :bordered="false" loading><div style="height: 180px"></div></Card>
      <Collapse v-if="record" class="advanced-panel" :bordered="false"><CollapsePanel key="sql" header="SQL 与查询口径"><pre class="sql-block">{{ record.normalized_sql || record.generated?.sql }}</pre><p>{{ record.generated?.assumptions.join('；') }}</p></CollapsePanel><CollapsePanel key="trace" header="执行记录"><Timeline><TimelineItem v-for="(event, index) in record.timeline" :key="index">{{ event.message }} <span class="muted">{{ new Date(event.at).toLocaleTimeString('zh-CN') }}</span></TimelineItem></Timeline></CollapsePanel></Collapse>
    </div>
  </Page>
</template>

<style scoped>
.workbench{display:grid;gap:20px;max-width:1440px}.query-card,.chart-card,.detail-card,.metric-card,.empty-card,.approval-card{border:1px solid #e7edf5;border-radius:14px;box-shadow:0 8px 28px rgba(28,53,87,.05)}.query-card{padding:8px 8px 0;background:linear-gradient(135deg,#fff 0%,#f7fbff 100%)}.query-card__top,.query-card__footer,.result-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap}.query-card__top{padding:14px 16px 24px}.eyebrow{color:#3b76d3;font-size:11px;font-weight:700;letter-spacing:1.2px}.query-card h1{margin:8px 0 7px;color:#16365d;font-size:27px;letter-spacing:-.7px}.query-card p,.result-heading p{margin:0;color:#73839a;font-size:13px}.status-tag{margin-top:5px}.field-label{display:block;padding:0 16px 8px;color:#263d5c;font-size:13px;font-weight:600}.query-card :deep(.ant-input){border-color:#d9e3ef;border-radius:10px;padding:12px 14px;resize:vertical}.query-card__footer{align-items:center;padding:15px 16px 12px}.muted,.metric-note{color:#7b8ba1;font-size:12px}.shortcut{margin-left:8px;font-size:11px;opacity:.72}.source-line{padding:0 16px 17px;color:#8190a5;font-size:12px}.source-line span{margin:0 7px}.source-dot{display:inline-block;width:7px;height:7px;margin-right:5px;border-radius:50%;background:#18a999}.approval-card{background:#fffaf0}.result-heading{align-items:end;padding:5px 3px 0}.result-heading h2{margin:7px 0 4px;color:#16365d;font-size:25px}.metric-grid{display:grid;grid-template-columns:1.35fr 1fr 1fr 1fr;gap:16px}.metric-card{padding:2px;background:#fff}.metric-card--primary{background:linear-gradient(135deg,#173e68,#2565a3);color:#fff}.metric-label{margin-bottom:12px;color:#74849a;font-size:12px}.metric-card--primary .metric-label,.metric-card--primary .metric-note{color:#c3d6ed}.metric-card :deep(.ant-statistic-content){font-size:25px;font-weight:650;font-variant-numeric:tabular-nums}.metric-card--primary :deep(.ant-statistic-content){color:#fff}.metric-card :deep(.ant-statistic-content-suffix){font-size:12px;font-weight:400}.metric-note{margin-top:9px}.result-grid{display:grid;grid-template-columns:minmax(0,2.2fr) minmax(290px,1fr);gap:16px}.card-title{display:flex;align-items:center;gap:12px}.card-title span{color:#8a98aa;font-size:12px;font-weight:400}.chart-card :deep(.ant-card-body){padding-top:3px}.detail-item{display:grid;gap:7px;padding:15px 0;border-bottom:1px solid #edf1f6}.detail-item:first-child{padding-top:0}.detail-item:last-child{border-bottom:0}.detail-item span{color:#8492a5;font-size:12px}.detail-item strong{color:#294361;font-size:13px;font-weight:500;line-height:1.6}.result-alert{margin-top:-4px}.empty-card{text-align:center;padding:42px 20px;background:#fbfcfe}.empty-icon{display:grid;place-items:center;width:46px;height:46px;margin:0 auto 12px;border-radius:14px;background:#eaf2ff;color:#3976f6;font-size:26px}.empty-card h3{margin:0 0 6px;color:#294361;font-size:16px}.empty-card p{margin:0;color:#8a98aa;font-size:13px}.advanced-panel{margin-top:-3px;background:transparent}.sql-block{max-height:240px;overflow:auto;border-radius:8px;background:#f5f7fa;padding:14px;color:#40546e;font-size:12px;line-height:1.65}@media(max-width:1100px){.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.result-grid{grid-template-columns:1fr}}@media(max-width:600px){.metric-grid{grid-template-columns:1fr}.query-card h1{font-size:23px}.query-card__footer{align-items:stretch}.query-card__footer :deep(.ant-btn){width:100%}}
</style>
