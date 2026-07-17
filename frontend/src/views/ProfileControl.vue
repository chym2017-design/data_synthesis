<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h2 style="margin: 0">用户画像控制</h2>
      <el-button type="primary" @click="generateSampleProfile" :loading="generating">
        随机生成示例画像
      </el-button>
    </div>
    <p style="color: #666; margin-bottom: 20px">控制用户画像生成的所有概率参数。点击「随机生成示例画像」可预览当前配置下生成的用户画像。</p>

    <!-- 示例画像预览对话框 -->
    <el-dialog v-model="showProfileDialog" title="示例用户画像预览" width="900px" top="3vh">
      <div v-if="sampleProfile" style="max-height: 80vh; overflow-y: auto; font-size: 14px; line-height: 1.8">
        <!-- 基本信息 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">基本信息</h4>
        <el-descriptions :column="3" border size="small" style="margin-bottom: 12px">
          <el-descriptions-item label="姓名">{{ sampleProfile.basic_info?.name }}</el-descriptions-item>
          <el-descriptions-item label="性别">{{ sampleProfile.basic_info?.gender }}</el-descriptions-item>
          <el-descriptions-item label="年龄">{{ sampleProfile.basic_info?.age }}岁</el-descriptions-item>
          <el-descriptions-item label="职业">{{ sampleProfile.basic_info?.occupation }}</el-descriptions-item>
          <el-descriptions-item label="学历">{{ sampleProfile.basic_info?.education }}</el-descriptions-item>
          <el-descriptions-item label="婚姻">{{ sampleProfile.basic_info?.marital_status }}</el-descriptions-item>
          <el-descriptions-item label="城市">{{ sampleProfile.basic_info?.city }}</el-descriptions-item>
          <el-descriptions-item label="客户层级">{{ sampleProfile.basic_info?.customer_tier }}</el-descriptions-item>
          <el-descriptions-item label="风险偏好">{{ sampleProfile.basic_info?.risk_tolerance }}/5</el-descriptions-item>
        </el-descriptions>

        <!-- 资产总览 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">资产总览</h4>
        <el-descriptions :column="4" border size="small" style="margin-bottom: 12px">
          <el-descriptions-item label="总资产">{{ formatMoney(sampleProfile.asset_summary?.total_assets) }}</el-descriptions-item>
          <el-descriptions-item label="总负债">{{ formatMoney(sampleProfile.asset_summary?.total_liability) }}</el-descriptions-item>
          <el-descriptions-item label="净资产">{{ formatMoney(sampleProfile.asset_summary?.net_assets) }}</el-descriptions-item>
          <el-descriptions-item label="资产负债率">{{ ((sampleProfile.asset_summary?.debt_ratio || 0) * 100).toFixed(1) }}%</el-descriptions-item>
        </el-descriptions>

        <!-- 借记卡 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">借记卡</h4>
        <el-table :data="sampleProfile.accounts?.debit_cards || []" border size="small" style="margin-bottom: 12px" empty-text="无">
          <el-table-column label="等级" prop="card_level" width="80" />
          <el-table-column label="账户类型" prop="account_type" width="100" />
          <el-table-column label="余额" width="120"><template #default="{ row }">{{ formatMoney(row.balance) }}</template></el-table-column>
          <el-table-column label="可用余额" width="120"><template #default="{ row }">{{ formatMoney(row.available_balance) }}</template></el-table-column>
          <el-table-column label="状态" prop="status" width="80" />
          <el-table-column label="开户行" prop="branch" />
        </el-table>

        <!-- 信用卡 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">信用卡</h4>
        <el-table :data="sampleProfile.accounts?.credit_cards || []" border size="small" style="margin-bottom: 12px" empty-text="无">
          <el-table-column label="卡名" prop="card_name" width="200" />
          <el-table-column label="类型" prop="card_type" width="80" />
          <el-table-column label="额度" width="100"><template #default="{ row }">{{ formatMoney(row.limit) }}</template></el-table-column>
          <el-table-column label="已用" width="100"><template #default="{ row }">{{ formatMoney(row.used_limit) }}</template></el-table-column>
          <el-table-column label="账单日" prop="bill_day" width="80" />
          <el-table-column label="状态" prop="status" width="80" />
        </el-table>

        <!-- 存款 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">存款持仓</h4>
        <el-table :data="sampleProfile.investments?.deposits?.holdings || []" border size="small" style="margin-bottom: 12px" empty-text="无">
          <el-table-column label="类型" prop="deposit_type" width="100" />
          <el-table-column label="金额" width="120"><template #default="{ row }">{{ formatMoney(row.amount) }}</template></el-table-column>
          <el-table-column label="期限(月)" prop="term_months" width="80" />
          <el-table-column label="年利率" width="100"><template #default="{ row }">{{ (row.annual_rate * 100).toFixed(2) }}%</template></el-table-column>
        </el-table>

        <!-- 基金 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">基金持仓</h4>
        <el-table :data="sampleProfile.investments?.fund?.holdings || []" border size="small" style="margin-bottom: 12px" empty-text="无">
          <el-table-column label="基金名称" prop="fund_name" width="180" />
          <el-table-column label="类型" prop="fund_type" width="100" />
          <el-table-column label="市值" width="120"><template #default="{ row }">{{ formatMoney(row.market_value) }}</template></el-table-column>
          <el-table-column label="盈亏" width="150"><template #default="{ row }"><span :style="{ color: row.profit_loss >= 0 ? '#67C23A' : '#F56C6C' }">{{ formatMoney(row.profit_loss) }} ({{ row.profit_loss_rate.toFixed(1) }}%)</span></template></el-table-column>
        </el-table>

        <!-- 理财 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">理财持仓</h4>
        <el-table :data="sampleProfile.investments?.wealth_management?.holdings || []" border size="small" style="margin-bottom: 12px" empty-text="无">
          <el-table-column label="产品名" prop="product_name" width="180" />
          <el-table-column label="类型" prop="product_type" width="100" />
          <el-table-column label="金额" width="120"><template #default="{ row }">{{ formatMoney(row.amount) }}</template></el-table-column>
          <el-table-column label="剩余天数" prop="remaining_days" width="100" />
        </el-table>

        <!-- 保险 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">保险持仓</h4>
        <el-table :data="sampleProfile.investments?.insurance?.policies || []" border size="small" style="margin-bottom: 12px" empty-text="无">
          <el-table-column label="产品名" prop="product_name" width="200" />
          <el-table-column label="分类" prop="category" width="100" />
          <el-table-column label="保额" width="120"><template #default="{ row }">{{ formatMoney(row.coverage) }}</template></el-table-column>
          <el-table-column label="年缴" width="100"><template #default="{ row }">{{ formatMoney(row.premium) }}</template></el-table-column>
        </el-table>

        <!-- 国债 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">国债持仓</h4>
        <el-table :data="sampleProfile.investments?.bonds?.holdings || []" border size="small" style="margin-bottom: 12px" empty-text="无">
          <el-table-column label="名称" prop="bond_name" width="220" />
          <el-table-column label="类型" prop="bond_type" width="120" />
          <el-table-column label="金额" width="120"><template #default="{ row }">{{ formatMoney(row.amount) }}</template></el-table-column>
          <el-table-column label="年利率" width="100"><template #default="{ row }">{{ (row.annual_rate * 100).toFixed(2) }}%</template></el-table-column>
        </el-table>

        <!-- 贵金属 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">贵金属</h4>
        <el-table :data="sampleProfile.investments?.precious_metals?.holdings || []" border size="small" style="margin-bottom: 12px" empty-text="无">
          <el-table-column label="名称" prop="name" width="120" />
          <el-table-column label="数量" prop="quantity" width="80" />
          <el-table-column label="成本" width="100"><template #default="{ row }">{{ formatMoney(row.avg_cost) }}</template></el-table-column>
          <el-table-column label="市值" width="100"><template #default="{ row }">{{ formatMoney(row.market_value) }}</template></el-table-column>
          <el-table-column label="盈亏" width="120"><template #default="{ row }"><span :style="{ color: row.profit_loss >= 0 ? '#67C23A' : '#F56C6C' }">{{ formatMoney(row.profit_loss) }}</span></template></el-table-column>
        </el-table>

        <!-- 贷款 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">贷款信息</h4>
        <el-table :data="sampleProfile.loans?.list || []" border size="small" style="margin-bottom: 12px" empty-text="无">
          <el-table-column label="类型" prop="loan_type" width="100" />
          <el-table-column label="金额" width="120"><template #default="{ row }">{{ formatMoney(row.amount) }}</template></el-table-column>
          <el-table-column label="月供" width="100"><template #default="{ row }">{{ formatMoney(row.monthly_payment) }}</template></el-table-column>
          <el-table-column label="剩余期限" width="100"><template #default="{ row }">{{ row.remaining_months }}个月</template></el-table-column>
          <el-table-column label="状态" prop="status" width="80" />
        </el-table>

        <!-- 收款人 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">收款人</h4>
        <el-table :data="sampleProfile.payees?.list || []" border size="small" style="margin-bottom: 12px" empty-text="无">
          <el-table-column label="姓名" prop="name" width="120" />
          <el-table-column label="关系" prop="relation" width="80" />
          <el-table-column label="银行" prop="bank_name" width="120" />
          <el-table-column label="常用" width="60"><template #default="{ row }">{{ row.is_frequent ? '是' : '否' }}</template></el-table-column>
        </el-table>

        <!-- 安全设置 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">安全设置</h4>
        <el-descriptions :column="3" border size="small" style="margin-bottom: 12px">
          <el-descriptions-item label="认证方式">{{ (sampleProfile.security?.media?.auth_methods || []).join('、') }}</el-descriptions-item>
          <el-descriptions-item label="U盾">{{ sampleProfile.security?.media?.has_udun ? '有' : '无' }}</el-descriptions-item>
          <el-descriptions-item label="单笔限额">{{ formatMoney(sampleProfile.security?.limits?.single_limit) }}</el-descriptions-item>
          <el-descriptions-item label="日累计限额">{{ formatMoney(sampleProfile.security?.limits?.daily_limit) }}</el-descriptions-item>
          <el-descriptions-item label="夜间锁">{{ sampleProfile.security?.account_lock?.night_lock ? '开启' : '关闭' }}</el-descriptions-item>
          <el-descriptions-item label="境外锁">{{ sampleProfile.security?.account_lock?.overseas_lock ? '开启' : '关闭' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 权益 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">权益信息</h4>
        <el-descriptions :column="3" border size="small" style="margin-bottom: 12px">
          <el-descriptions-item label="星级">{{ sampleProfile.benefits?.star_level }}</el-descriptions-item>
          <el-descriptions-item label="星点值">{{ sampleProfile.benefits?.star_points?.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item label="i豆">{{ sampleProfile.benefits?.i_dou_balance?.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item label="优惠券">{{ sampleProfile.benefits?.coupons }}张</el-descriptions-item>
          <el-descriptions-item label="绿色能量">{{ sampleProfile.benefits?.green_energy?.toLocaleString() }}</el-descriptions-item>
        </el-descriptions>

        <!-- 民生 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">民生服务</h4>
        <el-descriptions :column="2" border size="small" style="margin-bottom: 12px">
          <el-descriptions-item label="社保">{{ sampleProfile.livelihood?.has_social_security ? '已绑定' : '未绑定' }}</el-descriptions-item>
          <el-descriptions-item label="医保">{{ sampleProfile.livelihood?.has_medical_insurance ? '已绑定' : '未绑定' }}</el-descriptions-item>
          <el-descriptions-item label="公积金">{{ sampleProfile.livelihood?.has_housing_fund ? '已绑定' : '未绑定' }}</el-descriptions-item>
          <el-descriptions-item label="个人养老金">{{ sampleProfile.livelihood?.has_personal_pension ? '已开通' : '未开通' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 薪资 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">薪资信息</h4>
        <el-descriptions :column="2" border size="small" style="margin-bottom: 12px" v-if="sampleProfile.salary">
          <el-descriptions-item label="月工资">{{ formatMoney(sampleProfile.salary?.monthly_salary) }}</el-descriptions-item>
          <el-descriptions-item label="发薪日">每月{{ sampleProfile.salary?.salary_payment_day }}日</el-descriptions-item>
          <el-descriptions-item label="单位">{{ sampleProfile.salary?.company_name || '无' }}</el-descriptions-item>
        </el-descriptions>
        <div v-else style="color: #999; margin-bottom: 12px">无薪资信息（企业主/自由职业者）</div>

        <!-- 支付代扣 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">支付代扣</h4>
        <el-table :data="sampleProfile.payment_agreements || []" border size="small" style="margin-bottom: 12px" empty-text="无">
          <el-table-column label="类型" prop="type" width="80" />
          <el-table-column label="供应商" prop="provider" width="160" />
          <el-table-column label="限额" width="100"><template #default="{ row }">{{ row.limit_per_time }}</template></el-table-column>
          <el-table-column label="状态" prop="status" width="80" />
        </el-table>

        <!-- 数字人民币 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">数字人民币</h4>
        <el-descriptions :column="2" border size="small" style="margin-bottom: 12px" v-if="sampleProfile.digital_rmb">
          <el-descriptions-item label="钱包类型">{{ sampleProfile.digital_rmb?.wallet_type }}</el-descriptions-item>
          <el-descriptions-item label="余额">{{ formatMoney(sampleProfile.digital_rmb?.balance) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ sampleProfile.digital_rmb?.status }}</el-descriptions-item>
          <el-descriptions-item label="自动充值">{{ sampleProfile.digital_rmb?.auto_recharge ? '已开启' : '未开启' }}</el-descriptions-item>
        </el-descriptions>
        <div v-else style="color: #999; margin-bottom: 12px">无</div>

        <!-- 投资偏好 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">投资偏好</h4>
        <el-descriptions :column="2" border size="small" style="margin-bottom: 12px">
          <el-descriptions-item label="风险偏好">{{ sampleProfile.investment_profile?.risk_appetite }}</el-descriptions-item>
          <el-descriptions-item label="投资经验">{{ sampleProfile.investment_profile?.investment_experience }}年</el-descriptions-item>
          <el-descriptions-item label="持仓周期">{{ sampleProfile.investment_profile?.holding_period }}个月</el-descriptions-item>
          <el-descriptions-item label="投资频率">{{ sampleProfile.investment_profile?.investment_frequency }}</el-descriptions-item>
        </el-descriptions>

        <!-- 行为特征 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">使用习惯</h4>
        <el-descriptions :column="2" border size="small" style="margin-bottom: 12px">
          <el-descriptions-item label="APP版本">{{ sampleProfile.behavior?.app_version }}</el-descriptions-item>
          <el-descriptions-item label="登录频率">{{ sampleProfile.behavior?.login_frequency }}</el-descriptions-item>
          <el-descriptions-item label="常用渠道" :span="2">{{ (sampleProfile.behavior?.preferred_channels || []).join('、') }}</el-descriptions-item>
          <el-descriptions-item label="常用菜单" :span="2">{{ (sampleProfile.behavior?.frequent_menus || []).join('、') }}</el-descriptions-item>
        </el-descriptions>

        <!-- 近期交易 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">近期交易记录（前10条）</h4>
        <el-table :data="(sampleProfile.recent_transactions || []).slice(0, 10)" border size="small" style="margin-bottom: 12px" empty-text="无">
          <el-table-column label="类型" prop="type" width="80" />
          <el-table-column label="金额" width="120"><template #default="{ row }"><span :style="{ color: row.amount >= 0 ? '#67C23A' : '#F56C6C' }">{{ formatMoney(row.amount) }}</span></template></el-table-column>
          <el-table-column label="对方" prop="counterparty" width="120" />
          <el-table-column label="时间" prop="trans_time" width="180" />
        </el-table>

        <!-- Markdown 原始格式 -->
        <h4 style="margin: 16px 0 8px; color: #409EFF">Markdown 格式</h4>
        <div style="background: #f5f7fa; border: 1px solid #e4e7ed; border-radius: 4px; padding: 16px; white-space: pre-wrap; font-family: 'Courier New', monospace; font-size: 13px; line-height: 1.6; max-height: 600px; overflow-y: auto">{{ profileMarkdown }}</div>
      </div>
      <template #footer>
        <el-button type="primary" @click="generateSampleProfile">重新生成</el-button>
        <el-button @click="showProfileDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 基本属性 -->
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>基本属性</span>
          <el-button size="small" @click="redistributeBasic">概率重分布</el-button>
        </div>
      </template>
      <el-form label-width="180px" size="small">
        <el-form-item>
          <template #label>年龄范围<el-tooltip content="生成用户画像时的年龄范围下限和上限" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="basic.ageMin" :min="18" :max="70" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="basic.ageMax" :min="18" :max="70" size="small" style="width: 100px" />
          <span style="color: #999; margin-left: 8px">岁</span>
        </el-form-item>
        <el-form-item>
          <template #label>风险承受范围<el-tooltip content="用户风险承受能力评估的最小和最大值（1-5）" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="basic.riskMin" :min="1" :max="5" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="basic.riskMax" :min="1" :max="5" size="small" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <template #label>学历分布<el-tooltip content="不同学历的权重" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-table :data="educationList" border size="small" style="width: 100%">
            <el-table-column label="学历" width="120"><template #default="{ row }">{{ row.label }}</template></el-table-column>
            <el-table-column label="权重"><template #default="{ row }"><el-input-number v-model="basic.educationWeights[row.key]" :min="0" :max="10" :step="0.1" size="small" style="width: 140px" /></template></el-table-column>
          </el-table>
        </el-form-item>
        <el-form-item>
          <template #label>婚姻状态<el-tooltip content="不同婚姻状态的权重" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-table :data="maritalList" border size="small" style="width: 100%">
            <el-table-column label="状态" width="120"><template #default="{ row }">{{ row.label }}</template></el-table-column>
            <el-table-column label="权重"><template #default="{ row }"><el-input-number v-model="basic.maritalWeights[row.key]" :min="0" :max="10" :step="0.1" size="small" style="width: 140px" /></template></el-table-column>
          </el-table>
        </el-form-item>
        <el-form-item>
          <template #label>客户层级<el-tooltip content="客户层级权重" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-table :data="customerTierList" border size="small" style="width: 100%">
            <el-table-column label="层级" width="120"><template #default="{ row }">{{ row.label }}</template></el-table-column>
            <el-table-column label="权重"><template #default="{ row }"><el-input-number v-model="basic.customerTierWeights[row.key]" :min="0" :max="1" :step="0.01" size="small" style="width: 140px" /></template></el-table-column>
          </el-table>
        </el-form-item>
        <el-form-item>
          <template #label>有子女概率<el-tooltip content="用户有子女的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="basic.hasChildrenProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>办卡地与常住地一致<el-tooltip content="用户办卡城市与常住城市相同的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="basic.isSameCityProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>手机号段<el-tooltip content="生成用户手机号时可选的号段前缀" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="phonePrefixesStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 借记卡 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>借记卡</span>
          <el-button size="small" @click="redistributeDebit">概率重分布</el-button>
        </div>
      </template>
      <el-form label-width="180px" size="small">
        <el-form-item>
          <template #label>卡片等级<el-tooltip content="借记卡卡片等级权重" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-table :data="debitLevelList" border size="small" style="width: 100%">
            <el-table-column label="等级" width="120"><template #default="{ row }">{{ row.label }}</template></el-table-column>
            <el-table-column label="权重"><template #default="{ row }"><el-input-number v-model="debitCard.levelWeights[row.key]" :min="0" :max="1" :step="0.01" size="small" style="width: 140px" /></template></el-table-column>
          </el-table>
        </el-form-item>
        <el-form-item>
          <template #label>账户类型<el-tooltip content="借记卡账户类型权重（I类/II类/III类户）" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-table :data="accountTypeList" border size="small" style="width: 100%">
            <el-table-column label="类型" width="140"><template #default="{ row }">{{ row.label }}</template></el-table-column>
            <el-table-column label="权重"><template #default="{ row }"><el-input-number v-model="debitCard.accountTypeWeights[row.key]" :min="0" :max="1" :step="0.01" size="small" style="width: 140px" /></template></el-table-column>
          </el-table>
        </el-form-item>
        <el-form-item>
          <template #label>卡片状态<el-tooltip content="借记卡状态权重" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-table :data="debitStatusList" border size="small" style="width: 100%">
            <el-table-column label="状态" width="120"><template #default="{ row }">{{ row.label }}</template></el-table-column>
            <el-table-column label="权重"><template #default="{ row }"><el-input-number v-model="debitCard.statusWeights[row.key]" :min="0" :max="1" :step="0.01" size="small" style="width: 140px" /></template></el-table-column>
          </el-table>
        </el-form-item>
        <el-form-item>
          <template #label>仅1张卡概率<el-tooltip content="用户只持有1张借记卡的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="debitCard.singleProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>多卡用户最多<el-tooltip content="多卡用户最多可持有的借记卡数量" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="debitCard.multiMax" :min="1" :max="10" size="small" />
          <span style="margin-left: 8px; color: #999">张</span>
        </el-form-item>
        <el-form-item>
          <template #label>年费减免概率<el-tooltip content="年费被减免的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="debitCard.annualFeeWaivedProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>年龄系数<el-tooltip content="年龄对卡片数量的影响系数范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="debitCard.ageFactorMin" :min="0" :max="2" :step="0.1" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="debitCard.ageFactorMax" :min="0" :max="2" :step="0.1" size="small" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <template #label>可用余额比例<el-tooltip content="可用余额 = balance × 此比例范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="debitCard.availBalanceRatioMin" :min="0" :max="1" :step="0.01" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="debitCard.availBalanceRatioMax" :min="0" :max="1" :step="0.01" size="small" style="width: 100px" />
        </el-form-item>
        <el-divider style="margin: 12px 0">各等级余额分布</el-divider>
        <el-table :data="balanceDistList" border size="small">
          <el-table-column label="卡片等级" width="120"><template #default="{ row }">{{ row.label }}</template></el-table-column>
          <el-table-column label="余额分布（JSON格式）" min-width="400">
            <template #default="{ row }">
              <el-input v-model="balanceDistJson[row.key]" size="small" type="textarea" :rows="3" />
            </template>
          </el-table-column>
        </el-table>
      </el-form>
    </el-card>

    <!-- 信用卡 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>信用卡</span>
          <el-button size="small" @click="redistributeObj(creditCard.statusWeights)">概率重分布</el-button>
        </div>
      </template>
      <el-form label-width="180px" size="small">
        <el-form-item>
          <template #label>持有概率<el-tooltip content="用户持有信用卡的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="creditCard.hasProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>自动还款概率<el-tooltip content="信用卡开通自动还款的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="creditCard.autoRepayProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>有积分概率<el-tooltip content="信用卡有未使用积分的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="creditCard.hasPointsProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>积分范围<el-tooltip content="信用卡积分的最小/最大值" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="creditCard.pointsMin" :min="0" :step="1000" size="small" style="width: 120px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="creditCard.pointsMax" :min="0" :step="1000" size="small" style="width: 120px" />
        </el-form-item>
        <el-form-item>
          <template #label>卡片状态<el-tooltip content="信用卡状态权重" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-table :data="creditStatusList" border size="small" style="width: 100%">
            <el-table-column label="状态" width="120"><template #default="{ row }">{{ row.label }}</template></el-table-column>
            <el-table-column label="权重"><template #default="{ row }"><el-input-number v-model="creditCard.statusWeights[row.key]" :min="0" :max="1" :step="0.01" size="small" style="width: 140px" /></template></el-table-column>
          </el-table>
        </el-form-item>
        <el-form-item>
          <template #label>额度使用比例<el-tooltip content="已使用额度占总额度的比例范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="creditCard.usedLimitRatioMin" :min="0" :max="1" :step="0.01" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="creditCard.usedLimitRatioMax" :min="0" :max="1" :step="0.01" size="small" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <template #label>账单日可选<el-tooltip content="信用卡可选账单日期列表" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="billDaysStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
        <el-divider style="margin: 12px 0">年龄对应卡数</el-divider>
        <el-table :data="ageCreditCountList" border size="small">
          <el-table-column label="年龄段" width="120"><template #default="{ row }">{{ row.label }}</template></el-table-column>
          <el-table-column label="最少"><template #default="{ row }"><el-input-number v-model="row.data[0]" :min="0" :max="10" size="small" style="width: 100px" /></template></el-table-column>
          <el-table-column label="最多"><template #default="{ row }"><el-input-number v-model="row.data[1]" :min="0" :max="10" size="small" style="width: 100px" /></template></el-table-column>
        </el-table>
        <el-divider style="margin: 12px 0">高额度配置</el-divider>
        <el-form-item>
          <template #label>高额度年龄<el-tooltip content="高于此年龄可获高额度" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="creditCard.highLimitAge" :min="18" :max="65" size="small" />
          <span style="color: #999; margin-left: 8px">岁以上</span>
        </el-form-item>
        <el-form-item>
          <template #label>高额度倍数<el-tooltip content="高额度用户的额度倍数范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="creditCard.highLimitMultMin" :min="0" :max="20" :step="0.5" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="creditCard.highLimitMultMax" :min="0" :max="20" :step="0.5" size="small" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <template #label>中额度年龄<el-tooltip content="高于此年龄可获中额度" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="creditCard.midLimitAge" :min="18" :max="65" size="small" />
          <span style="color: #999; margin-left: 8px">岁以上</span>
        </el-form-item>
        <el-form-item>
          <template #label>中额度倍数<el-tooltip content="中额度用户的额度倍数范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="creditCard.midLimitMultMin" :min="0" :max="20" :step="0.5" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="creditCard.midLimitMultMax" :min="0" :max="20" :step="0.5" size="small" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <template #label>高额度职业<el-tooltip content="更容易获得高额度的职业列表" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <div style="margin-bottom: 8px"><el-tag v-for="(occ, i) in creditCard.highLimitOccupations" :key="i" closable @close="creditCard.highLimitOccupations.splice(i, 1)" style="margin: 4px">{{ occ }}</el-tag></div>
          <el-input v-model="creditCard.newHighLimitOcc" size="small" style="width: 200px; margin-right: 8px" @keyup.enter="addHighLimitOcc" />
          <el-button size="small" @click="addHighLimitOcc">添加</el-button>
        </el-form-item>
        <el-divider style="margin: 12px 0">信用卡产品池</el-divider>
        <el-table :data="creditCard.products" border size="small">
          <el-table-column label="产品名称" min-width="200"><template #default="{ row }"><el-input v-model="row.name" size="small" /></template></el-table-column>
          <el-table-column label="类型" width="120"><template #default="{ row }"><el-input v-model="row.type" size="small" /></template></el-table-column>
          <el-table-column label="基础额度" width="120"><template #default="{ row }"><el-input-number v-model="row.base_limit" :min="0" :step="5000" size="small" style="width: 100px" /></template></el-table-column>
          <el-table-column label="操作" width="80"><template #default="{ $index }"><el-button size="small" type="danger" text @click="creditCard.products.splice($index, 1)">删除</el-button></template></el-table-column>
        </el-table>
        <el-button size="small" style="margin-top: 8px" @click="creditCard.products.push({ name: '', type: '', base_limit: 0 })">新增产品</el-button>
      </el-form>
    </el-card>

    <!-- 收款人 -->
    <el-card style="margin-top: 16px">
      <template #header><span>收款人</span></template>
      <el-form label-width="180px" size="small">
        <el-form-item>
          <template #label>有收款人概率<el-tooltip content="用户有常用收款人的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="payees.hasProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>收款人数量<el-tooltip content="收款人数量范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="payees.countMin" :min="0" :max="20" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="payees.countMax" :min="0" :max="20" size="small" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <template #label>常用收款人概率<el-tooltip content="标记为常用收款人的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="payees.isFrequentProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>有手机号概率<el-tooltip content="收款人有手机号的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="payees.hasPhoneProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>商户池<el-tooltip content="常见收款商户列表" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="merchantPoolStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
        <el-form-item>
          <template #label>还款名称<el-tooltip content="还款类收款人名称" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="repaymentNamesStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 持仓概率 -->
    <el-card style="margin-top: 16px">
      <template #header><span>持仓概率</span></template>
      <el-table :data="holdingsList" border size="small">
        <el-table-column label="类型" width="140"><template #default="{ row }">{{ row.label }}</template></el-table-column>
        <el-table-column label="概率">
          <template #default="{ row }">
            <el-tooltip :content="holdingTooltips[row.key]" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-right: 4px"><QuestionFilled /></el-icon></el-tooltip>
            <el-input-number v-model="holdings[row.key]" :min="0" :max="1" :step="0.01" size="small" style="width: 140px" />
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 持仓数量 -->
    <el-card style="margin-top: 16px">
      <template #header><span>持仓数量</span></template>
      <el-form label-width="180px" size="small">
        <el-form-item>
          <template #label>基金最大/风险等级<el-tooltip content="每风险等级最多持有的基金数" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="holdingsCount.fundMaxPerRisk" :min="1" :max="20" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>理财最大/风险等级<el-tooltip content="每风险等级最多持有的理财数" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="holdingsCount.wealthMaxPerRisk" :min="1" :max="20" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>保险数量<el-tooltip content="保险持有数量范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="holdingsCount.insuranceMin" :min="0" :max="10" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="holdingsCount.insuranceMax" :min="0" :max="10" size="small" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <template #label>国债数量<el-tooltip content="国债持有数量范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="holdingsCount.bondMin" :min="0" :max="10" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="holdingsCount.bondMax" :min="0" :max="10" size="small" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <template #label>贵金属数量<el-tooltip content="贵金属持有数量范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="holdingsCount.metalsMin" :min="0" :max="10" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="holdingsCount.metalsMax" :min="0" :max="10" size="small" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <template #label>贷款最大数量/年龄<el-tooltip content="贷款最大数量 = max(1, min(此值, age//20))" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="holdingsCount.loanMaxByAge" :min="1" :max="10" size="small" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 存款 -->
    <el-card style="margin-top: 16px">
      <template #header><span>存款</span></template>
      <el-form label-width="180px" size="small">
        <el-divider style="margin: 0 0 12px">大额存单</el-divider>
        <el-form-item>
          <template #label>有大额存单概率<el-tooltip content="用户有大额存单的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="deposits.hasLargeProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>大额存单数量<el-tooltip content="大额存单持有数量范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="deposits.largeCountMin" :min="0" :max="10" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="deposits.largeCountMax" :min="0" :max="10" size="small" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <template #label>大额存单期限(月)<el-tooltip content="可选的大额存单期限列表" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="largeTermsStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
        <el-form-item>
          <template #label>大额存单金额范围<el-tooltip content="大额存单金额范围（元）" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="deposits.largeAmountMin" :min="0" :step="10000" size="small" style="width: 120px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="deposits.largeAmountMax" :min="0" :step="10000" size="small" style="width: 120px" />
        </el-form-item>
        <el-form-item>
          <template #label>大额存单利率范围<el-tooltip content="大额存单年化利率范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="deposits.largeRateMin" :min="0" :max="0.1" :step="0.001" size="small" style="width: 120px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="deposits.largeRateMax" :min="0" :max="0.1" :step="0.001" size="small" style="width: 120px" />
        </el-form-item>

        <el-divider style="margin: 0 0 12px">定期存款</el-divider>
        <el-form-item>
          <template #label>有定期存款概率<el-tooltip content="用户有定期存款的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="deposits.hasFixedProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>定期存款数量<el-tooltip content="定期存款持有数量范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="deposits.fixedCountMin" :min="0" :max="10" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="deposits.fixedCountMax" :min="0" :max="10" size="small" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <template #label>定期存款期限(月)<el-tooltip content="可选的定期存款期限列表" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="fixedTermsStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
        <el-form-item>
          <template #label>定期存款金额范围<el-tooltip content="定期存款金额范围（元）" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="deposits.fixedAmountMin" :min="0" :step="1000" size="small" style="width: 120px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="deposits.fixedAmountMax" :min="0" :step="1000" size="small" style="width: 120px" />
        </el-form-item>
        <el-form-item>
          <template #label>定期存款利率范围<el-tooltip content="定期存款年化利率范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="deposits.fixedRateMin" :min="0" :max="0.1" :step="0.001" size="small" style="width: 120px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="deposits.fixedRateMax" :min="0" :max="0.1" :step="0.001" size="small" style="width: 120px" />
        </el-form-item>
        <el-form-item>
          <template #label>自动转存概率<el-tooltip content="定期存款到期自动转存的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="deposits.autoRolloverProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 贷款 -->
    <el-card style="margin-top: 16px">
      <template #header><span>贷款</span></template>
      <el-form label-width="180px" size="small">
        <el-form-item>
          <template #label>逾期概率<el-tooltip content="贷款有逾期记录的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="loans.overdueProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>房贷抵扣个税概率<el-tooltip content="房贷利息用于个人所得税抵扣的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="loans.isMortgageDeductibleProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>还款方式<el-tooltip content="可选的还款方式" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="repaymentMethodsStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
        <el-divider style="margin: 0 0 12px">利率范围</el-divider>
        <el-form-item v-for="lt in loanRateList" :key="lt.key">
          <template #label>{{ lt.label }}<el-tooltip :content="`${lt.label}利率范围`" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="loanRates[lt.key][0]" :min="0" :max="0.2" :step="0.001" size="small" style="width: 120px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="loanRates[lt.key][1]" :min="0" :max="0.2" :step="0.001" size="small" style="width: 120px" />
        </el-form-item>
        <el-divider style="margin: 0 0 12px">贷款类型</el-divider>
        <el-table :data="loans.loanTypes" border size="small">
          <el-table-column label="类型" min-width="140"><template #default="{ row }"><el-input v-model="row.type" size="small" /></template></el-table-column>
          <el-table-column label="最低金额" width="120"><template #default="{ row }"><el-input-number v-model="row.min_amount" :min="0" :step="10000" size="small" style="width: 100px" /></template></el-table-column>
          <el-table-column label="最高金额" width="120"><template #default="{ row }"><el-input-number v-model="row.max_amount" :min="0" :step="10000" size="small" style="width: 100px" /></template></el-table-column>
          <el-table-column label="最低期限" width="100"><template #default="{ row }"><el-input-number v-model="row.min_term" :min="0" :max="360" size="small" style="width: 80px" /></template></el-table-column>
          <el-table-column label="最高期限" width="100"><template #default="{ row }"><el-input-number v-model="row.max_term" :min="0" :max="360" size="small" style="width: 80px" /></template></el-table-column>
          <el-table-column label="操作" width="80"><template #default="{ $index }"><el-button size="small" type="danger" text @click="loans.loanTypes.splice($index, 1)">删除</el-button></template></el-table-column>
        </el-table>
        <el-button size="small" style="margin-top: 8px" @click="loans.loanTypes.push({ type: '', min_amount: 0, max_amount: 0, min_term: 0, max_term: 0 })">新增类型</el-button>
      </el-form>
    </el-card>

    <!-- 安全设置 -->
    <el-card style="margin-top: 16px">
      <template #header><span>安全设置</span></template>
      <el-form label-width="180px" size="small">
        <el-form-item>
          <template #label>U盾持有概率<el-tooltip content="用户持有U盾的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="security.hasUdunProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>U盾品牌<el-tooltip content="可选的U盾品牌列表" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="udunBrandsStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
        <el-form-item>
          <template #label>U盾状态<el-tooltip content="U盾状态权重" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-table :data="udunStatusList" border size="small" style="width: 100%">
            <el-table-column label="状态" width="120"><template #default="{ row }">{{ row.label }}</template></el-table-column>
            <el-table-column label="权重"><template #default="{ row }"><el-input-number v-model="security.udunStatusWeights[row.key]" :min="0" :max="1" :step="0.01" size="small" style="width: 140px" /></template></el-table-column>
          </el-table>
        </el-form-item>
        <el-form-item>
          <template #label>指纹认证概率<el-tooltip content="用户开通指纹认证的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="security.fingerprintProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>刷脸认证概率<el-tooltip content="用户开通刷脸认证的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="security.faceAuthProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>夜间锁概率<el-tooltip content="用户开启夜间交易锁的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="security.nightLockProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>境外锁概率<el-tooltip content="用户开启境外交易锁的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="security.overseasLockProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>在线支付锁概率<el-tooltip content="用户开启在线支付锁的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="security.onlinePayLockProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 服务概率 -->
    <el-card style="margin-top: 16px">
      <template #header><span>服务概率</span></template>
      <el-table :data="serviceList" border size="small">
        <el-table-column label="服务" width="140"><template #default="{ row }">{{ row.label }}</template></el-table-column>
        <el-table-column label="概率">
          <template #default="{ row }">
            <el-tooltip :content="serviceTooltips[row.key]" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-right: 4px"><QuestionFilled /></el-icon></el-tooltip>
            <el-input-number v-model="service[row.key]" :min="0" :max="1" :step="0.01" size="small" style="width: 140px" />
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 权益 -->
    <el-card style="margin-top: 16px">
      <template #header><span>权益</span></template>
      <el-form label-width="180px" size="small">
        <el-form-item>
          <template #label>有i豆概率<el-tooltip content="用户拥有i豆的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="benefits.hasIDouProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>i豆范围<el-tooltip content="用户i豆余额范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="benefits.iDouMin" :min="0" :step="100" size="small" style="width: 120px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="benefits.iDouMax" :min="0" :step="100" size="small" style="width: 120px" />
        </el-form-item>
        <el-form-item>
          <template #label>即将过期i豆<el-tooltip content="即将过期的i豆数量范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="benefits.iDouExpiringMin" :min="0" :step="10" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="benefits.iDouExpiringMax" :min="0" :step="10" size="small" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <template #label>优惠券数量<el-tooltip content="用户拥有的优惠券数量范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="benefits.couponsMin" :min="0" :max="50" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="benefits.couponsMax" :min="0" :max="50" size="small" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <template #label>星级列表<el-tooltip content="可选的会员星级" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="starLevelsStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
        <el-form-item>
          <template #label>星点值范围<el-tooltip content="用户星点值范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="benefits.starPointsMin" :min="0" :step="1000" size="small" style="width: 120px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="benefits.starPointsMax" :min="0" :step="1000" size="small" style="width: 120px" />
        </el-form-item>
        <el-form-item>
          <template #label>绿色能量范围<el-tooltip content="用户绿色能量值范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="benefits.greenEnergyMin" :min="0" :step="100" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="benefits.greenEnergyMax" :min="0" :step="100" size="small" style="width: 100px" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 数字人民币 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>数字人民币</span>
          <el-button size="small" @click="redistributeDigitalRmb">概率重分布</el-button>
        </div>
      </template>
      <el-form label-width="180px" size="small">
        <el-form-item>
          <template #label>钱包类型<el-tooltip content="数字人民币钱包类型权重" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-table :data="walletTypeList" border size="small" style="width: 100%">
            <el-table-column label="类型" width="120"><template #default="{ row }">{{ row.label }}</template></el-table-column>
            <el-table-column label="权重"><template #default="{ row }"><el-input-number v-model="digitalRmb.walletTypeWeights[row.key]" :min="0" :max="1" :step="0.01" size="small" style="width: 140px" /></template></el-table-column>
          </el-table>
        </el-form-item>
        <el-form-item>
          <template #label>自动充值概率<el-tooltip content="数字人民币钱包自动充值的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="digitalRmb.autoRechargeProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>钱包状态<el-tooltip content="数字人民币钱包状态权重" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-table :data="digitalRmbStatusList" border size="small" style="width: 100%">
            <el-table-column label="状态" width="120"><template #default="{ row }">{{ row.label }}</template></el-table-column>
            <el-table-column label="权重"><template #default="{ row }"><el-input-number v-model="digitalRmb.statusWeights[row.key]" :min="0" :max="1" :step="0.01" size="small" style="width: 140px" /></template></el-table-column>
          </el-table>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 薪资 -->
    <el-card style="margin-top: 16px">
      <template #header><span>薪资</span></template>
      <el-form label-width="180px" size="small">
        <el-form-item>
          <template #label>有工资卡概率<el-tooltip content="用户持有工资卡的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="salary.hasSalaryCardProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>有公司信息概率<el-tooltip content="用户有公司信息（如单位名）的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="salary.hasCompanyProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>发薪日<el-tooltip content="可选的发薪日期" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="paymentDaysStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
        <el-form-item>
          <template #label>排除职业<el-tooltip content="不生成工资信息的职业" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="excludedOccupationsStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
        <el-divider style="margin: 0 0 12px">各职业薪资范围</el-divider>
        <el-table :data="salaryRangeList" border size="small">
          <el-table-column label="职业" width="140"><template #default="{ row }">{{ row.label }}</template></el-table-column>
          <el-table-column label="最低"><template #default="{ row }"><el-input-number v-model="salary.salaryRanges[row.key][0]" :min="0" :step="1000" size="small" style="width: 120px" /></template></el-table-column>
          <el-table-column label="最高"><template #default="{ row }"><el-input-number v-model="salary.salaryRanges[row.key][1]" :min="0" :step="1000" size="small" style="width: 120px" /></template></el-table-column>
        </el-table>
      </el-form>
    </el-card>

    <!-- 支付代扣 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>支付代扣</span>
          <el-button size="small" @click="redistributeObj(paymentAgreements.statusWeights)">概率重分布</el-button>
        </div>
      </template>
      <el-form label-width="180px" size="small">
        <el-form-item>
          <template #label>有代扣概率<el-tooltip content="用户有代扣协议的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="paymentAgreements.hasProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>代扣数量<el-tooltip content="代扣协议数量范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="paymentAgreements.countMin" :min="0" :max="20" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="paymentAgreements.countMax" :min="0" :max="20" size="small" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <template #label>已暂停概率<el-tooltip content="代扣协议处于暂停状态的概率" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="paymentAgreements.pausedProb" :min="0" :max="1" :step="0.01" size="small" />
        </el-form-item>
        <el-form-item>
          <template #label>限额选项<el-tooltip content="可选的代扣限额" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="limitOptionsStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
        <el-form-item>
          <template #label>协议状态<el-tooltip content="代扣协议状态权重" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-table :data="paymentStatusList" border size="small" style="width: 100%">
            <el-table-column label="状态" width="120"><template #default="{ row }">{{ row.label }}</template></el-table-column>
            <el-table-column label="权重"><template #default="{ row }"><el-input-number v-model="paymentAgreements.statusWeights[row.key]" :min="0" :max="1" :step="0.01" size="small" style="width: 140px" /></template></el-table-column>
          </el-table>
        </el-form-item>
        <el-form-item>
          <template #label>公用事业类型<el-tooltip content="水电气话费等代扣类型" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-table :data="paymentAgreements.utilityTypes" border size="small">
            <el-table-column label="类型" width="140"><template #default="{ row }"><el-input v-model="row.type" size="small" /></template></el-table-column>
            <el-table-column label="供应商" min-width="200"><template #default="{ row }"><el-input v-model="row.provider" size="small" /></template></el-table-column>
            <el-table-column label="操作" width="80"><template #default="{ $index }"><el-button size="small" type="danger" text @click="paymentAgreements.utilityTypes.splice($index, 1)">删除</el-button></template></el-table-column>
          </el-table>
          <el-button size="small" style="margin-top: 8px" @click="paymentAgreements.utilityTypes.push({ type: '', provider: '' })">新增</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 交易记录 -->
    <el-card style="margin-top: 16px">
      <template #header><span>交易记录</span></template>
      <el-form label-width="180px" size="small">
        <el-form-item>
          <template #label>交易数量<el-tooltip content="交易记录数量范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="transactions.countMin" :min="0" :max="100" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="transactions.countMax" :min="0" :max="100" size="small" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <template #label>交易类型<el-tooltip content="可选的交易类型" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="transactionsTypesStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
        <el-form-item>
          <template #label>交易金额范围<el-tooltip content="单笔交易金额范围（元）" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="transactions.amountMin" :min="0" :step="10" size="small" style="width: 120px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="transactions.amountMax" :min="0" :step="1000" size="small" style="width: 120px" />
        </el-form-item>
        <el-form-item>
          <template #label>回溯天数<el-tooltip content="交易记录回溯的天数范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="transactions.daysMin" :min="0" :max="365" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="transactions.daysMax" :min="0" :max="365" size="small" style="width: 100px" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 投资偏好 -->
    <el-card style="margin-top: 16px">
      <template #header><span>投资偏好</span></template>
      <el-tabs v-model="investPrefTab">
        <el-tab-pane v-for="level in riskLevels" :key="level" :label="level" :name="level">
          <el-form label-width="140px" size="small">
            <el-form-item label="基金类型"><el-input v-model="investFundTypesStr[level]" size="small" /><span style="color: #999; margin-left: 8px">逗号分隔</span></el-form-item>
            <el-form-item label="理财类型"><el-input v-model="investWealthTypesStr[level]" size="small" /><span style="color: #999; margin-left: 8px">逗号分隔</span></el-form-item>
            <el-form-item label="持有期限(月)">
              <el-input-number v-model="investPrefs[level].holdingMin" :min="0" :max="60" size="small" style="width: 100px" />
              <span style="margin: 0 8px">~</span>
              <el-input-number v-model="investPrefs[level].holdingMax" :min="0" :max="120" size="small" style="width: 100px" />
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 行为特征 -->
    <el-card style="margin-top: 16px">
      <template #header><span>行为特征</span></template>
      <el-form label-width="180px" size="small">
        <el-form-item>
          <template #label>APP版本(>55岁)<el-tooltip content="55岁以上用户可选的APP版本" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="appVersionOldStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
        <el-form-item>
          <template #label>APP版本(默认)<el-tooltip content="55岁及以下用户可选的APP版本" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="appVersionDefaultStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
        <el-form-item>
          <template #label>登录频率<el-tooltip content="用户登录频率选项" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="loginFreqStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
        <el-form-item>
          <template #label>渠道池<el-tooltip content="用户可选的交易渠道" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="channelPoolStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
        <el-form-item>
          <template #label>渠道数量<el-tooltip content="用户使用的渠道数量范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="behavior.channelCountMin" :min="1" :max="10" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="behavior.channelCountMax" :min="1" :max="10" size="small" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <template #label>常用菜单池<el-tooltip content="用户常用菜单选项" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input v-model="frequentMenuPoolStr" size="small" />
          <span style="color: #999; margin-left: 8px">逗号分隔</span>
        </el-form-item>
        <el-form-item>
          <template #label>常用菜单数量<el-tooltip content="用户常用菜单数量范围" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></template>
          <el-input-number v-model="behavior.frequentMenuMin" :min="1" :max="10" size="small" style="width: 100px" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="behavior.frequentMenuMax" :min="1" :max="10" size="small" style="width: 100px" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 产品池 -->
    <el-card style="margin-top: 16px">
      <template #header><span>产品池</span></template>
      <el-tabs v-model="productTab">
        <el-tab-pane label="保险产品" name="insurance">
          <el-table :data="insuranceProducts" border size="small">
            <el-table-column label="代码" width="100"><template #default="{ row }"><el-input v-model="row.code" size="small" /></template></el-table-column>
            <el-table-column label="名称" min-width="180"><template #default="{ row }"><el-input v-model="row.name" size="small" /></template></el-table-column>
            <el-table-column label="类型" width="120"><template #default="{ row }"><el-input v-model="row.type" size="small" /></template></el-table-column>
            <el-table-column label="分类" width="120"><template #default="{ row }"><el-input v-model="row.category" size="small" /></template></el-table-column>
            <el-table-column label="操作" width="80"><template #default="{ $index }"><el-button size="small" type="danger" text @click="insuranceProducts.splice($index, 1)">删除</el-button></template></el-table-column>
          </el-table>
          <el-button size="small" style="margin-top: 8px" @click="insuranceProducts.push({ code: '', name: '', type: '', category: '' })">新增</el-button>
        </el-tab-pane>
        <el-tab-pane label="国债产品" name="bond">
          <el-table :data="bondProducts" border size="small">
            <el-table-column label="代码" width="100"><template #default="{ row }"><el-input v-model="row.code" size="small" /></template></el-table-column>
            <el-table-column label="名称" min-width="250"><template #default="{ row }"><el-input v-model="row.name" size="small" /></template></el-table-column>
            <el-table-column label="类型" width="120"><template #default="{ row }"><el-input v-model="row.type" size="small" /></template></el-table-column>
            <el-table-column label="操作" width="80"><template #default="{ $index }"><el-button size="small" type="danger" text @click="bondProducts.splice($index, 1)">删除</el-button></template></el-table-column>
          </el-table>
          <el-button size="small" style="margin-top: 8px" @click="bondProducts.push({ code: '', name: '', type: '' })">新增</el-button>
        </el-tab-pane>
        <el-tab-pane label="贵金属" name="metals">
          <el-table :data="preciousMetals" border size="small">
            <el-table-column label="代码" width="100"><template #default="{ row }"><el-input v-model="row.code" size="small" /></template></el-table-column>
            <el-table-column label="名称" width="140"><template #default="{ row }"><el-input v-model="row.name" size="small" /></template></el-table-column>
            <el-table-column label="类型" width="120"><template #default="{ row }"><el-input v-model="row.type" size="small" /></template></el-table-column>
            <el-table-column label="单位" width="80"><template #default="{ row }"><el-input v-model="row.unit" size="small" /></template></el-table-column>
            <el-table-column label="操作" width="80"><template #default="{ $index }"><el-button size="small" type="danger" text @click="preciousMetals.splice($index, 1)">删除</el-button></template></el-table-column>
          </el-table>
          <el-button size="small" style="margin-top: 8px" @click="preciousMetals.push({ code: '', name: '', type: '', unit: '' })">新增</el-button>
        </el-tab-pane>
        <el-tab-pane label="基金产品池" name="fund">
          <div style="display: flex; gap: 12px; margin-bottom: 12px; align-items: center">
            <el-upload accept=".csv" :show-file-list="false" :before-upload="handleFundUpload" :http-request="uploadCsv">
              <el-button size="small" type="primary">导入 CSV</el-button>
            </el-upload>
            <el-select v-model="selectedFundCsv" placeholder="选择产品池" clearable size="small" style="width: 300px" @change="onCsvChange">
              <el-option label="使用默认产品池（内置）" value="" />
              <el-option v-for="r in availableFundResources" :key="r.path" :label="`${r.filename}（${r.rows}条）`" :value="r.path" />
            </el-select>
            <span v-if="fundTotalRows !== null" style="color: #909399; font-size: 13px">共 {{ fundTotalRows }} 条</span>
          </div>
          <el-table :data="fundPreviewData" border size="small" max-height="400" v-loading="fundPreviewLoading">
            <el-table-column label="代码" prop="code" width="100" />
            <el-table-column label="名称" prop="fund_name" min-width="200" />
            <el-table-column label="类型" prop="fund_type" width="150" />
          </el-table>
          <div v-if="fundTotalRows > fundPreviewData.length" style="color: #909399; font-size: 12px; margin-top: 4px">仅显示前 {{ fundPreviewData.length }} 条</div>
        </el-tab-pane>
        <el-tab-pane label="理财产品池" name="wealth">
          <div style="display: flex; gap: 12px; margin-bottom: 12px; align-items: center">
            <el-upload accept=".csv" :show-file-list="false" :before-upload="handleWealthUpload" :http-request="uploadCsv">
              <el-button size="small" type="primary">导入 CSV</el-button>
            </el-upload>
            <el-select v-model="selectedWealthCsv" placeholder="选择产品池" clearable size="small" style="width: 300px" @change="onCsvChange">
              <el-option label="使用默认产品池（内置）" value="" />
              <el-option v-for="r in availableWealthResources" :key="r.path" :label="`${r.filename}（${r.rows}条）`" :value="r.path" />
            </el-select>
            <span v-if="wealthTotalRows !== null" style="color: #909399; font-size: 13px">共 {{ wealthTotalRows }} 条</span>
          </div>
          <el-table :data="wealthPreviewData" border size="small" max-height="400" v-loading="wealthPreviewLoading">
            <el-table-column label="名称" prop="product_name" min-width="300" />
            <el-table-column label="收益率" prop="product_yield" width="150" />
          </el-table>
          <div v-if="wealthTotalRows > wealthPreviewData.length" style="color: #909399; font-size: 12px; margin-top: 4px">仅显示前 {{ wealthPreviewData.length }} 条</div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <div style="margin-top: 20px">
      <el-button type="primary" @click="saveAll" :loading="saving">保存所有配置</el-button>
      <el-button type="warning" plain @click="restoreDefault" :loading="restoring">恢复默认</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import api from '../api/index.js'

// ========== 基本属性 ==========
const basic = ref({
  customerTierWeights: { 普通: 0.6, 优质: 0.3, 高净值: 0.1 },
  educationWeights: { '高中及以下': 1, '大专': 1, '本科': 2, '硕士': 1, '博士': 0.5 },
  maritalWeights: { 未婚: 1, 已婚: 1, 离异: 0.3 },
  hasChildrenProb: 0.5,
  isSameCityProb: 0.7,
  ageMin: 18, ageMax: 70,
  riskMin: 1, riskMax: 5,
  phonePrefixes: ['138', '139', '136', '137', '135', '150', '151', '152', '157', '158', '159', '182', '183', '187', '188'],
})

// ========== 借记卡 ==========
const debitCard = ref({
  levelWeights: { 普卡: 0.60, 金卡: 0.25, 白金卡: 0.12, 钻石卡: 0.03 },
  accountTypeWeights: { 'I类户_主': 0.60, 'I类户_次': 0.15, 'I类户_三': 0.15, 'II类户_主': 0.05, 'II类户_次': 0.03, 'III类户': 0.02 },
  statusWeights: { 正常: 0.67, 挂失: 0.17, 冻结: 0.17 },
  singleProb: 0.55,
  multiMax: 4,
  annualFeeWaivedProb: 0.7,
  ageFactorMin: 0.3, ageFactorMax: 1.0,
  availBalanceRatioMin: 0.9, availBalanceRatioMax: 1.0,
  balanceDistribution: {
    普卡: { '<100': 0.20, '100-1000': 0.30, '1000-10000': 0.35, '10000-30000': 0.10, '>30000': 0.05 },
    金卡: { '1000-5000': 0.15, '5000-20000': 0.30, '20000-80000': 0.30, '80000-300000': 0.25 },
    白金卡: { '5000-20000': 0.05, '20000-100000': 0.20, '100000-500000': 0.35, '500000-1500000': 0.40 },
    钻石卡: { '20000-100000': 0.10, '100000-500000': 0.30, '500000-5000000': 0.60 },
  },
})

// ========== 信用卡 ==========
const creditCard = ref({
  hasProb: 0.7,
  autoRepayProb: 0.75,
  hasPointsProb: 0.7,
  statusWeights: { 正常: 0.67, 未激活: 0.17, 已冻结: 0.17 },
  usedLimitRatioMin: 0.1, usedLimitRatioMax: 0.8,
  billDays: [1, 5, 10, 15, 20, 25],
  highLimitOccupations: ['企业主', '金融从业者', 'IT工程师'],
  highLimitAge: 35,
  highLimitMultMin: 2, highLimitMultMax: 5,
  midLimitAge: 30,
  midLimitMultMin: 1.2, midLimitMultMax: 2,
  pointsMin: 0, pointsMax: 50000,
  ageCreditCount: { '<25': [1, 2], '25-40': [1, 4], '>40': [1, 3] },
  products: [],
})

// ========== 收款人 ==========
const payees = ref({
  hasProb: 0.7,
  countMin: 3, countMax: 8,
  isFrequentProb: 0.5,
  hasPhoneProb: 0.5,
  merchantPool: ['京东', '淘宝', '拼多多', '美团', '滴滴', '支付宝', '微信'],
  repaymentNames: ['房贷还款', '车贷还款', '信用卡还款'],
})

// ========== 持仓概率 ==========
const holdings = ref({
  has_fund: 0.6, has_wealth: 0.5, has_insurance: 0.5,
  has_bond: 0.3, has_metals: 0.2, has_loan: 0.6, has_payees: 0.7,
})

// ========== 持仓数量 ==========
const holdingsCount = ref({
  fundMaxPerRisk: 5,
  wealthMaxPerRisk: 4,
  insuranceMin: 1, insuranceMax: 3,
  bondMin: 1, bondMax: 2,
  metalsMin: 1, metalsMax: 3,
  loanMaxByAge: 3,
})

// ========== 存款 ==========
const deposits = ref({
  hasLargeProb: 0.7, largeCountMin: 1, largeCountMax: 3,
  largeTerms: [12, 24, 36],
  largeAmountMin: 200000, largeAmountMax: 1000000,
  largeRateMin: 0.0225, largeRateMax: 0.035,
  hasFixedProb: 0.8, fixedCountMin: 1, fixedCountMax: 3,
  fixedTerms: [3, 6, 12, 24, 36, 60],
  fixedAmountMin: 10000, fixedAmountMax: 500000,
  fixedRateMin: 0.015, fixedRateMax: 0.03,
  autoRolloverProb: 0.67,
})

// ========== 贷款 ==========
const loans = ref({
  rateRanges: { '购房贷款': [0.035, 0.045], '信用贷款': [0.04, 0.08], '其他': [0.035, 0.06] },
  repaymentMethods: ['等额本息', '等额本金', '先息后本'],
  overdueProb: 0.1,
  isMortgageDeductibleProb: 0.5,
  loanTypes: [],
})

// ========== 安全设置 ==========
const security = ref({
  hasUdunProb: 0.5, udunBrands: ['飞天诚信', '天地融', '华大'],
  udunStatusWeights: { 正常: 0.75, 即将到期: 0.25 },
  fingerprintProb: 0.7, faceAuthProb: 0.5,
  nightLockProb: 0.3, overseasLockProb: 0.2, onlinePayLockProb: 0.1,
})

// ========== 权益 ==========
const benefits = ref({
  hasIDouProb: 0.7, iDouMin: 0, iDouMax: 10000,
  iDouExpiringMin: 0, iDouExpiringMax: 500,
  couponsMin: 0, couponsMax: 10,
  starLevels: ['一星', '二星', '三星', '四星', '五星', '六星', '七星'],
  starPointsMin: 0, starPointsMax: 100000,
  greenEnergyMin: 0, greenEnergyMax: 5000,
})

// ========== 服务概率 ==========
const service = ref({
  has_social_security: 0.8, has_medical_insurance: 0.9,
  has_housing_fund: 0.7, has_personal_pension: 0.4,
})

// ========== 数字人民币 ==========
const digitalRmb = ref({
  walletTypeWeights: { '一类钱包': 0.1, '二类钱包': 0.3, '三类钱包': 0.4, '四类钱包': 0.2 },
  autoRechargeProb: 0.5,
  statusWeights: { 正常: 0.75, 已停用: 0.25 },
})

// ========== 薪资 ==========
const salary = ref({
  hasSalaryCardProb: 0.8,
  excludedOccupations: ['企业主', '自由职业者'],
  salaryRanges: {
    'IT工程师': [15000, 50000], '医生': [10000, 50000], '教师': [5000, 20000],
    '公务员': [8000, 30000], '金融从业者': [15000, 60000], '学生': [0, 3000],
    '退休人员': [3000, 10000], '销售': [5000, 30000], '默认': [5000, 20000],
  },
  hasCompanyProb: 0.7,
  paymentDays: [5, 10, 15, 20, 25],
})

// ========== 支付代扣 ==========
const paymentAgreements = ref({
  hasProb: 0.7, countMin: 1, countMax: 4,
  pausedProb: 0.25,
  limitOptions: [500, 1000, 2000, 5000],
  statusWeights: { 生效中: 0.75, 已暂停: 0.25 },
  utilityTypes: [],
})

// ========== 交易记录 ==========
const transactions = ref({
  countMin: 5, countMax: 20,
  types: ['转账', '消费', '缴费', '理财购买', '工资', '还款', '退款'],
  amountMin: 10, amountMax: 50000,
  daysMin: 0, daysMax: 30,
})

// ========== 投资偏好 ==========
const investPrefs = ref({
  '保守': { fundTypes: [], wealthTypes: [], holdingMin: 12, holdingMax: 36 },
  '稳健': { fundTypes: [], wealthTypes: [], holdingMin: 12, holdingMax: 36 },
  '平衡': { fundTypes: [], wealthTypes: [], holdingMin: 6, holdingMax: 24 },
  '成长': { fundTypes: [], wealthTypes: [], holdingMin: 3, holdingMax: 12 },
  '积极': { fundTypes: [], wealthTypes: [], holdingMin: 3, holdingMax: 12 },
})
const investFundTypesStr = ref({ 保守: '', 稳健: '', 平衡: '', 成长: '', 积极: '' })
const investWealthTypesStr = ref({ 保守: '', 稳健: '', 平衡: '', 成长: '', 积极: '' })

// ========== 行为特征 ==========
const behavior = ref({
  appVersionOld: ['标准版', '创新版', '幸福生活版'],
  appVersionDefault: ['标准版', '创新版'],
  loginFreq: ['每日', '每周数次', '每月数次'],
  channelPool: ['手机银行', '网上银行', 'ATM', '柜台'],
  channelCountMin: 1, channelCountMax: 3,
  frequentMenuPool: ['查余额', '转账汇款', '理财', '信用卡还款', '基金', '缴费'],
  frequentMenuMin: 3, frequentMenuMax: 5,
})

// ========== 产品池 ==========
const insuranceProducts = ref([])
const bondProducts = ref([])
const preciousMetals = ref([])

// ========== UI 状态 ==========
const saving = ref(false)
const restoring = ref(false)
const balanceDistJson = ref({})
const loanRates = ref({ '购房贷款': [0.035, 0.045], '信用贷款': [0.04, 0.08], '其他': [0.035, 0.06] })
const investPrefTab = ref('保守')
const productTab = ref('insurance')

// ========== 示例画像预览 ==========
const showProfileDialog = ref(false)
const generating = ref(false)
const sampleProfile = ref(null)

// ========== 产品池 CSV 选择 ==========
const allResources = ref({})
const selectedFundCsv = ref('')
const selectedWealthCsv = ref('')

// 预览数据
const fundPreviewData = ref([])
const wealthPreviewData = ref([])
const fundTotalRows = ref(null)
const wealthTotalRows = ref(null)
const fundPreviewLoading = ref(false)
const wealthPreviewLoading = ref(false)

const availableFundResources = computed(() => {
  const r = allResources.value.fund
  return r ? [r] : []
})
const availableWealthResources = computed(() => {
  const r = allResources.value.financial_product
  return r ? [r] : []
})
const fundCsvInfo = computed(() => {
  if (!selectedFundCsv.value) return null
  return availableFundResources.value.find(r => r.path === selectedFundCsv.value)
})
const wealthCsvInfo = computed(() => {
  if (!selectedWealthCsv.value) return null
  return availableWealthResources.value.find(r => r.path === selectedWealthCsv.value)
})

async function loadResources() {
  try {
    const res = await api.config.listResources()
    allResources.value = res.data.resources || {}
    // 设置默认 CSV 路径
    if (allResources.value.fund && !selectedFundCsv.value) {
      selectedFundCsv.value = allResources.value.fund.path
    }
    if (allResources.value.financial_product && !selectedWealthCsv.value) {
      selectedWealthCsv.value = allResources.value.financial_product.path
    }
  } catch {
    allResources.value = {}
  }
}

function onCsvChange() {
  // 切换 CSV 后重新生成画像
  if (sampleProfile.value) {
    generateSampleProfile()
  }
}

async function uploadCsv(options) {
  try {
    const res = await api.config.uploadCsv(options.file)
    ElMessage.success(`CSV 上传成功: ${res.data.rows} 条`)
    await loadResources()
  } catch (e) {
    ElMessage.error('上传失败: ' + (e.response?.data?.detail || e.message))
  }
}

function handleFundUpload(file) {
  uploadCsv({ file })
  return false
}

function handleWealthUpload(file) {
  uploadCsv({ file })
  return false
}

async function loadFundPreview() {
  fundPreviewLoading.value = true
  try {
    const path = selectedFundCsv.value || '../../resources/fund.csv'
    const res = await api.config.csvPreview(path)
    fundPreviewData.value = res.data.preview
    fundTotalRows.value = res.data.total_rows
  } catch (e) {
    ElMessage.error('基金产品池预览失败: ' + (e.response?.data?.detail || e.message))
    fundPreviewData.value = []
  } finally {
    fundPreviewLoading.value = false
  }
}

async function loadWealthPreview() {
  wealthPreviewLoading.value = true
  try {
    const path = selectedWealthCsv.value || '../../resources/financial_product.csv'
    const res = await api.config.csvPreview(path)
    wealthPreviewData.value = res.data.preview
    wealthTotalRows.value = res.data.total_rows
  } catch (e) {
    ElMessage.error('理财产品池预览失败: ' + (e.response?.data?.detail || e.message))
    wealthPreviewData.value = []
  } finally {
    wealthPreviewLoading.value = false
  }
}

// 切换产品池标签时自动加载预览
watch(productTab, (tab) => {
  if (tab === 'fund') loadFundPreview()
  else if (tab === 'wealth') loadWealthPreview()
})

// 切换 CSV 选择时重新加载预览
watch(selectedFundCsv, () => {
  if (productTab.value === 'fund') loadFundPreview()
})
watch(selectedWealthCsv, () => {
  if (productTab.value === 'wealth') loadWealthPreview()
})

function formatMoney(val) {
  if (val == null || isNaN(val)) return '0.00元'
  const abs = Math.abs(val)
  const sign = val < 0 ? '-' : ''
  if (abs >= 100000000) return sign + (abs / 100000000).toFixed(2) + '亿元'
  if (abs >= 10000) return sign + (abs / 10000).toFixed(2) + '万元'
  return sign + abs.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '元'
}

const profileMarkdown = computed(() => {
  const p = sampleProfile.value
  if (!p) return ''
  const b = p.basic_info || {}
  const a = p.asset_summary || {}
  const lines = []
  lines.push(`# 用户画像 — ${b.name}`)
  lines.push('')
  lines.push(`- **性别**: ${b.gender}  |  **年龄**: ${b.age}岁  |  **职业**: ${b.occupation}`)
  lines.push(`- **学历**: ${b.education}  |  **婚姻**: ${b.marital_status}  |  **城市**: ${b.city}`)
  lines.push(`- **客户层级**: ${b.customer_tier}  |  **风险偏好**: ${b.risk_tolerance}/5`)
  lines.push('')
  lines.push(`## 资产总览`)
  lines.push(`- 总资产: ${formatMoney(a.total_assets)}  |  总负债: ${formatMoney(a.total_liability)}`)
  lines.push(`- 净资产: ${formatMoney(a.net_assets)}  |  资产负债率: ${(a.debt_ratio * 100).toFixed(1)}%`)
  lines.push('')
  // 借记卡
  lines.push('## 借记卡')
  ;(p.accounts?.debit_cards || []).forEach((c, i) => {
    lines.push(`| 卡片${i + 1} | ${c.card_level} | ${c.account_type} | 余额: ${formatMoney(c.balance)} | 状态: ${c.status} |`)
  })
  if (!p.accounts?.debit_cards?.length) lines.push('无')
  lines.push('')
  // 信用卡
  if ((p.accounts?.credit_cards || []).length > 0) {
    lines.push('## 信用卡')
    ;(p.accounts.credit_cards || []).forEach((c, i) => {
      lines.push(`| ${c.card_name} | ${c.card_type} | 额度: ${formatMoney(c.limit)} | 已用: ${formatMoney(c.used_limit)} | 状态: ${c.status} |`)
    })
    lines.push('')
  }
  // 存款
  if ((p.investments?.deposits?.holdings || []).length > 0) {
    lines.push('## 存款持仓')
    ;(p.investments.deposits.holdings || []).forEach(d => {
      lines.push(`| ${d.deposit_type} | 金额: ${formatMoney(d.amount)} | 期限: ${d.term_months}月 | 利率: ${(d.annual_rate * 100).toFixed(2)}% |`)
    })
    lines.push('')
  }
  // 基金
  if ((p.investments?.fund?.holdings || []).length > 0) {
    lines.push('## 基金持仓')
    ;(p.investments.fund.holdings || []).forEach(f => {
      lines.push(`| ${f.fund_name} | ${f.fund_type} | 市值: ${formatMoney(f.market_value)} | 盈亏: ${formatMoney(f.profit_loss)} (${f.profit_loss_rate.toFixed(1)}%) |`)
    })
    lines.push('')
  }
  // 理财
  if ((p.investments?.wealth_management?.holdings || []).length > 0) {
    lines.push('## 理财持仓')
    ;(p.investments.wealth_management.holdings || []).forEach(w => {
      lines.push(`| ${w.product_name} | ${w.product_type} | 金额: ${formatMoney(w.amount)} | 剩余: ${w.remaining_days}天 |`)
    })
    lines.push('')
  }
  // 保险
  if ((p.investments?.insurance?.policies || []).length > 0) {
    lines.push('## 保险持仓')
    ;(p.investments.insurance.policies || []).forEach(i => {
      lines.push(`| ${i.product_name} | ${i.category} | 保额: ${formatMoney(i.coverage)} | 年缴: ${formatMoney(i.premium)} |`)
    })
    lines.push('')
  }
  // 国债
  if ((p.investments?.bonds?.holdings || []).length > 0) {
    lines.push('## 国债持仓')
    ;(p.investments.bonds.holdings || []).forEach(b => {
      lines.push(`| ${b.bond_name} | ${b.bond_type} | 金额: ${formatMoney(b.amount)} | 利率: ${(b.annual_rate * 100).toFixed(2)}% |`)
    })
    lines.push('')
  }
  // 贵金属
  if ((p.investments?.precious_metals?.holdings || []).length > 0) {
    lines.push('## 贵金属')
    ;(p.investments.precious_metals.holdings || []).forEach(m => {
      lines.push(`| ${m.name} | ${m.quantity}${m.unit} | 成本: ${formatMoney(m.avg_cost)} | 市值: ${formatMoney(m.market_value)} |`)
    })
    lines.push('')
  }
  // 贷款
  if ((p.loans?.list || []).length > 0) {
    lines.push('## 贷款')
    ;(p.loans.list || []).forEach(l => {
      lines.push(`| ${l.loan_type} | 金额: ${formatMoney(l.amount)} | 月供: ${formatMoney(l.monthly_payment)} | 剩余: ${l.remaining_months}月 | 状态: ${l.status} |`)
    })
    lines.push('')
  }
  // 收款人
  if ((p.payees?.list || []).length > 0) {
    lines.push('## 收款人')
    ;(p.payees.list || []).forEach(pay => {
      lines.push(`| ${pay.name} | ${pay.relation} | ${pay.bank_name} | 常用: ${pay.is_frequent ? '是' : '否'} |`)
    })
    lines.push('')
  }
  // 安全
  const sec = p.security || {}
  lines.push('## 安全设置')
  lines.push(`- 认证方式: ${(sec.media?.auth_methods || []).join('、')}`)
  lines.push(`- U盾: ${sec.media?.has_udun ? '有' : '无'} | 单笔限额: ${formatMoney(sec.limits?.single_limit)} | 日限额: ${formatMoney(sec.limits?.daily_limit)}`)
  lines.push(`- 夜间锁: ${sec.account_lock?.night_lock ? '开启' : '关闭'} | 境外锁: ${sec.account_lock?.overseas_lock ? '开启' : '关闭'}`)
  lines.push('')
  // 权益
  const ben = p.benefits || {}
  lines.push('## 权益信息')
  lines.push(`- 星级: ${ben.star_level} | 星点值: ${ben.star_points?.toLocaleString()}`)
  lines.push(`- i豆: ${ben.i_dou_balance?.toLocaleString()} | 优惠券: ${ben.coupons}张 | 绿色能量: ${ben.green_energy?.toLocaleString()}`)
  lines.push('')
  // 民生
  const liv = p.livelihood || {}
  lines.push('## 民生服务')
  lines.push(`- 社保: ${liv.has_social_security ? '已绑定' : '未绑定'} | 医保: ${liv.has_medical_insurance ? '已绑定' : '未绑定'}`)
  lines.push(`- 公积金: ${liv.has_housing_fund ? '已绑定' : '未绑定'} | 个人养老金: ${liv.has_personal_pension ? '已开通' : '未开通'}`)
  lines.push('')
  // 薪资
  if (p.salary) {
    lines.push('## 薪资信息')
    lines.push(`- 月工资: ${formatMoney(p.salary.monthly_salary)} | 发薪日: 每月${p.salary.salary_payment_day}日 | 单位: ${p.salary.company_name || '无'}`)
    lines.push('')
  }
  // 支付代扣
  if ((p.payment_agreements || []).length > 0) {
    lines.push('## 支付代扣')
    ;(p.payment_agreements || []).forEach(pa => {
      lines.push(`| ${pa.type} | ${pa.provider} | 限额: ${pa.limit_per_time} | 状态: ${pa.status} |`)
    })
    lines.push('')
  }
  // 数字人民币
  if (p.digital_rmb) {
    lines.push('## 数字人民币')
    lines.push(`- 钱包类型: ${p.digital_rmb.wallet_type} | 余额: ${formatMoney(p.digital_rmb.balance)} | 状态: ${p.digital_rmb.status}`)
    lines.push('')
  }
  // 投资偏好
  const inv = p.investment_profile || {}
  lines.push('## 投资偏好')
  lines.push(`- 风险偏好: ${inv.risk_appetite} | 投资经验: ${inv.investment_experience}年 | 持仓周期: ${inv.holding_period}月 | 频率: ${inv.investment_frequency}`)
  lines.push('')
  // 行为
  const beh = p.behavior || {}
  lines.push('## 使用习惯')
  lines.push(`- APP版本: ${beh.app_version} | 登录频率: ${beh.login_frequency}`)
  lines.push(`- 常用渠道: ${(beh.preferred_channels || []).join('、')}`)
  lines.push(`- 常用菜单: ${(beh.frequent_menus || []).join('、')}`)
  lines.push('')
  // 近期交易
  if ((p.recent_transactions || []).length > 0) {
    lines.push('## 近期交易记录（前10条）')
    ;(p.recent_transactions || []).slice(0, 10).forEach(t => {
      lines.push(`| ${t.type} | ${formatMoney(t.amount)} | ${t.counterparty} | ${t.trans_time} |`)
    })
    lines.push('')
  }
  return lines.join('\n')
})

async function generateSampleProfile() {
  generating.value = true
  try {
    const csvOptions = {}
    if (selectedFundCsv.value) csvOptions.fund_csv = selectedFundCsv.value
    if (selectedWealthCsv.value) csvOptions.wealth_csv = selectedWealthCsv.value
    const res = await api.config.generateSampleProfile('bank_intent', csvOptions)
    sampleProfile.value = res.data.profile
    showProfileDialog.value = true
  } catch (e) {
    ElMessage.error('生成失败: ' + (e.message || e))
  } finally {
    generating.value = false
  }
}

const riskLevels = ['保守', '稳健', '平衡', '成长', '积极']

// ========== 计算列表 ==========
const customerTierList = computed(() => Object.keys(basic.value.customerTierWeights).map(k => ({ key: k, label: k })))
const educationList = computed(() => Object.keys(basic.value.educationWeights).map(k => ({ key: k, label: k })))
const maritalList = computed(() => Object.keys(basic.value.maritalWeights).map(k => ({ key: k, label: k })))
const debitLevelList = computed(() => Object.keys(debitCard.value.levelWeights).map(k => ({ key: k, label: k })))
const accountTypeList = computed(() => Object.keys(debitCard.value.accountTypeWeights).map(k => ({ key: k, label: k })))
const debitStatusList = computed(() => Object.keys(debitCard.value.statusWeights).map(k => ({ key: k, label: k })))
const balanceDistList = computed(() => Object.keys(debitCard.value.balanceDistribution).map(k => ({ key: k, label: k })))
const creditStatusList = computed(() => Object.keys(creditCard.value.statusWeights).map(k => ({ key: k, label: k })))
const ageCreditCountList = computed(() => Object.entries(creditCard.value.ageCreditCount).map(([k, v]) => ({ label: k, data: v })))
const holdingsList = [
  { key: 'has_fund', label: '基金持仓' }, { key: 'has_wealth', label: '理财持仓' },
  { key: 'has_insurance', label: '保险持仓' }, { key: 'has_bond', label: '国债持仓' },
  { key: 'has_metals', label: '贵金属持仓' }, { key: 'has_loan', label: '贷款信息' },
  { key: 'has_payees', label: '收款人' },
]
const holdingTooltips = {
  has_fund: '用户持有基金产品的概率', has_wealth: '用户持有银行理财产品的概率',
  has_insurance: '用户持有保险产品的概率', has_bond: '用户持有国债的概率',
  has_metals: '用户持有贵金属的概率', has_loan: '用户有贷款信息的概率',
  has_payees: '用户有常用收款人的概率',
}
const walletTypeList = computed(() => Object.keys(digitalRmb.value.walletTypeWeights).map(k => ({ key: k, label: k })))
const digitalRmbStatusList = computed(() => Object.keys(digitalRmb.value.statusWeights).map(k => ({ key: k, label: k })))
const paymentStatusList = computed(() => Object.keys(paymentAgreements.value.statusWeights).map(k => ({ key: k, label: k })))
const udunStatusList = computed(() => Object.keys(security.value.udunStatusWeights).map(k => ({ key: k, label: k })))
const serviceList = [
  { key: 'has_social_security', label: '社保' }, { key: 'has_medical_insurance', label: '医保' },
  { key: 'has_housing_fund', label: '公积金' }, { key: 'has_personal_pension', label: '个人养老金' },
]
const serviceTooltips = {
  has_social_security: '用户持有社保的概率', has_medical_insurance: '用户持有医保的概率',
  has_housing_fund: '用户持有公积金的概率', has_personal_pension: '用户开通个人养老金的概率',
}
const loanRateList = computed(() => Object.keys(loans.value.rateRanges).map(k => ({ key: k, label: k })))
const salaryRangeList = computed(() => Object.keys(salary.value.salaryRanges).map(k => ({ key: k, label: k })))

// 字符串辅助
function arrStr(arr) { return arr.join(', ') }
function strArr(str) { return str.split(',').map(s => s.trim()).filter(Boolean) }

// ========== Str refs for comma-separated arrays ==========
const phonePrefixesStr = ref(arrStr(basic.value.phonePrefixes))
const billDaysStr = ref(arrStr(creditCard.value.billDays))
const merchantPoolStr = ref(arrStr(payees.value.merchantPool))
const repaymentNamesStr = ref(arrStr(payees.value.repaymentNames))
const largeTermsStr = ref(arrStr(deposits.value.largeTerms))
const fixedTermsStr = ref(arrStr(deposits.value.fixedTerms))
const repaymentMethodsStr = ref(arrStr(loans.value.repaymentMethods))
const udunBrandsStr = ref(arrStr(security.value.udunBrands))
const starLevelsStr = ref(arrStr(benefits.value.starLevels))
const paymentDaysStr = ref(arrStr(salary.value.paymentDays))
const excludedOccupationsStr = ref(arrStr(salary.value.excludedOccupations))
const limitOptionsStr = ref(arrStr(paymentAgreements.value.limitOptions))
const transactionsTypesStr = ref(arrStr(transactions.value.types))
const appVersionOldStr = ref(arrStr(behavior.value.appVersionOld))
const appVersionDefaultStr = ref(arrStr(behavior.value.appVersionDefault))
const loginFreqStr = ref(arrStr(behavior.value.loginFreq))
const channelPoolStr = ref(arrStr(behavior.value.channelPool))
const frequentMenuPoolStr = ref(arrStr(behavior.value.frequentMenuPool))

// ========== 重分布 ==========
function redistributeObj(target) {
  const keys = Object.keys(target)
  const total = Object.values(target).reduce((a, b) => a + b, 0)
  if (total === 0) { const eq = 1 / keys.length; keys.forEach(k => { target[k] = eq }) }
  else { keys.forEach(k => { target[k] = target[k] / total }) }
  ElMessage.success('已重分布，总和=1.0')
}

// 基本属性：同时重分布学历、婚姻、客户层级
function redistributeBasic() {
  redistributeObj(basic.value.educationWeights)
  redistributeObj(basic.value.maritalWeights)
  redistributeObj(basic.value.customerTierWeights)
}

// 借记卡：同时重分布卡片等级、账户类型、状态
function redistributeDebit() {
  redistributeObj(debitCard.value.levelWeights)
  redistributeObj(debitCard.value.accountTypeWeights)
  redistributeObj(debitCard.value.statusWeights)
}

// 数字人民币：同时重分布钱包类型、状态
function redistributeDigitalRmb() {
  redistributeObj(digitalRmb.value.walletTypeWeights)
  redistributeObj(digitalRmb.value.statusWeights)
}

function addHighLimitOcc() {
  const v = creditCard.value.newHighLimitOcc?.trim()
  if (v && !creditCard.value.highLimitOccupations.includes(v)) {
    creditCard.value.highLimitOccupations.push(v)
    creditCard.value.newHighLimitOcc = ''
  }
}

// ========== 加载配置 ==========
onMounted(async () => {
  await loadResources()
  try {
    const res = await api.config.get('bank_intent', 'profile_config')
    const cfg = res.data.content

    if (cfg.basic_attributes) {
      const ba = cfg.basic_attributes
      if (ba.customer_tier_weights) basic.value.customerTierWeights = { ...ba.customer_tier_weights }
      if (ba.education_weights) basic.value.educationWeights = { ...ba.education_weights }
      if (ba.marital_weights) basic.value.maritalWeights = { ...ba.marital_weights }
      if (ba.has_children_prob !== undefined) basic.value.hasChildrenProb = ba.has_children_prob
      if (ba.is_same_city_prob !== undefined) basic.value.isSameCityProb = ba.is_same_city_prob
      if (ba.phone_prefixes) basic.value.phonePrefixes = [...ba.phone_prefixes]
      if (ba.age_range) { basic.value.ageMin = ba.age_range[0]; basic.value.ageMax = ba.age_range[1] }
      if (ba.risk_tolerance_range) { basic.value.riskMin = ba.risk_tolerance_range[0]; basic.value.riskMax = ba.risk_tolerance_range[1] }
    }

    if (cfg.debit_card) {
      const dc = cfg.debit_card
      if (dc.level_weights) debitCard.value.levelWeights = { ...dc.level_weights }
      if (dc.account_type_weights) debitCard.value.accountTypeWeights = { ...dc.account_type_weights }
      if (dc.status_weights) debitCard.value.statusWeights = { ...dc.status_weights }
      if (dc.count) {
        if (dc.count.single_prob !== undefined) debitCard.value.singleProb = dc.count.single_prob
        if (dc.count.multi_max !== undefined) debitCard.value.multiMax = dc.count.multi_max
      }
      if (dc.annual_fee_waived_prob !== undefined) debitCard.value.annualFeeWaivedProb = dc.annual_fee_waived_prob
      if (dc.age_factor_min !== undefined) debitCard.value.ageFactorMin = dc.age_factor_min
      if (dc.age_factor_max !== undefined) debitCard.value.ageFactorMax = dc.age_factor_max
      if (dc.available_balance_ratio) { debitCard.value.availBalanceRatioMin = dc.available_balance_ratio[0]; debitCard.value.availBalanceRatioMax = dc.available_balance_ratio[1] }
      if (dc.balance_distribution) {
        debitCard.value.balanceDistribution = { ...dc.balance_distribution }
        for (const k of Object.keys(dc.balance_distribution)) {
          balanceDistJson.value[k] = JSON.stringify(dc.balance_distribution[k], null, 2)
        }
      }
    }

    if (cfg.credit_card) {
      const cc = cfg.credit_card
      if (cc.has_probability !== undefined) creditCard.value.hasProb = cc.has_probability
      if (cc.auto_repayment_prob !== undefined) creditCard.value.autoRepayProb = cc.auto_repayment_prob
      if (cc.has_points_prob !== undefined) creditCard.value.hasPointsProb = cc.has_points_prob
      if (cc.status_weights) creditCard.value.statusWeights = { ...cc.status_weights }
      if (cc.used_limit_ratio) { creditCard.value.usedLimitRatioMin = cc.used_limit_ratio[0]; creditCard.value.usedLimitRatioMax = cc.used_limit_ratio[1] }
      if (cc.bill_days) creditCard.value.billDays = [...cc.bill_days]
      if (cc.high_limit_occupations) creditCard.value.highLimitOccupations = [...cc.high_limit_occupations]
      if (cc.high_limit_age !== undefined) creditCard.value.highLimitAge = cc.high_limit_age
      if (cc.high_limit_multiplier) { creditCard.value.highLimitMultMin = cc.high_limit_multiplier[0]; creditCard.value.highLimitMultMax = cc.high_limit_multiplier[1] }
      if (cc.mid_limit_age !== undefined) creditCard.value.midLimitAge = cc.mid_limit_age
      if (cc.mid_limit_multiplier) { creditCard.value.midLimitMultMin = cc.mid_limit_multiplier[0]; creditCard.value.midLimitMultMax = cc.mid_limit_multiplier[1] }
      if (cc.points_range) { creditCard.value.pointsMin = cc.points_range[0]; creditCard.value.pointsMax = cc.points_range[1] }
      if (cc.age_credit_count) creditCard.value.ageCreditCount = { ...cc.age_credit_count }
      if (cc.credit_products) creditCard.value.products = cc.credit_products.map(p => ({ ...p }))
    }

    if (cfg.payees) {
      const py = cfg.payees
      if (py.has_prob !== undefined) payees.value.hasProb = py.has_prob
      if (py.count_range) { payees.value.countMin = py.count_range[0]; payees.value.countMax = py.count_range[1] }
      if (py.is_frequent_prob !== undefined) payees.value.isFrequentProb = py.is_frequent_prob
      if (py.has_phone_prob !== undefined) payees.value.hasPhoneProb = py.has_phone_prob
      if (py.merchant_pool) payees.value.merchantPool = [...py.merchant_pool]
      if (py.repayment_names) payees.value.repaymentNames = [...py.repayment_names]
    }

    if (cfg.holdings_probability) {
      for (const key of Object.keys(holdings.value)) {
        if (cfg.holdings_probability[key] !== undefined) holdings.value[key] = cfg.holdings_probability[key]
      }
    }

    if (cfg.holdings_count) {
      const hc = cfg.holdings_count
      if (hc.fund_max_per_risk !== undefined) holdingsCount.value.fundMaxPerRisk = hc.fund_max_per_risk
      if (hc.wealth_max_per_risk !== undefined) holdingsCount.value.wealthMaxPerRisk = hc.wealth_max_per_risk
      if (hc.insurance_count) { holdingsCount.value.insuranceMin = hc.insurance_count[0]; holdingsCount.value.insuranceMax = hc.insurance_count[1] }
      if (hc.bond_count) { holdingsCount.value.bondMin = hc.bond_count[0]; holdingsCount.value.bondMax = hc.bond_count[1] }
      if (hc.metals_count) { holdingsCount.value.metalsMin = hc.metals_count[0]; holdingsCount.value.metalsMax = hc.metals_count[1] }
      if (hc.loan_max_by_age !== undefined) holdingsCount.value.loanMaxByAge = hc.loan_max_by_age
    }

    if (cfg.deposits) {
      const dp = cfg.deposits
      if (dp.has_large_deposit_prob !== undefined) deposits.value.hasLargeProb = dp.has_large_deposit_prob
      if (dp.large_deposit_count) { deposits.value.largeCountMin = dp.large_deposit_count[0]; deposits.value.largeCountMax = dp.large_deposit_count[1] }
      if (dp.large_deposit_terms) deposits.value.largeTerms = [...dp.large_deposit_terms]
      if (dp.large_deposit_range) { deposits.value.largeAmountMin = dp.large_deposit_range[0]; deposits.value.largeAmountMax = dp.large_deposit_range[1] }
      if (dp.large_deposit_rate_range) { deposits.value.largeRateMin = dp.large_deposit_rate_range[0]; deposits.value.largeRateMax = dp.large_deposit_rate_range[1] }
      if (dp.has_fixed_deposit_prob !== undefined) deposits.value.hasFixedProb = dp.has_fixed_deposit_prob
      if (dp.fixed_deposit_count) { deposits.value.fixedCountMin = dp.fixed_deposit_count[0]; deposits.value.fixedCountMax = dp.fixed_deposit_count[1] }
      if (dp.fixed_deposit_terms) deposits.value.fixedTerms = [...dp.fixed_deposit_terms]
      if (dp.fixed_deposit_range) { deposits.value.fixedAmountMin = dp.fixed_deposit_range[0]; deposits.value.fixedAmountMax = dp.fixed_deposit_range[1] }
      if (dp.fixed_deposit_rate_range) { deposits.value.fixedRateMin = dp.fixed_deposit_rate_range[0]; deposits.value.fixedRateMax = dp.fixed_deposit_rate_range[1] }
      if (dp.auto_rollover_prob !== undefined) deposits.value.autoRolloverProb = dp.auto_rollover_prob
    }

    if (cfg.loans) {
      const ln = cfg.loans
      if (ln.rate_ranges) {
        loans.value.rateRanges = { ...ln.rate_ranges }
        loanRates.value = { ...ln.rate_ranges }
      }
      if (ln.repayment_methods) loans.value.repaymentMethods = [...ln.repayment_methods]
      if (ln.overdue_prob !== undefined) loans.value.overdueProb = ln.overdue_prob
      if (ln.is_mortgage_tax_deductible_prob !== undefined) loans.value.isMortgageDeductibleProb = ln.is_mortgage_tax_deductible_prob
      if (ln.loan_types) loans.value.loanTypes = ln.loan_types.map(lt => ({ ...lt }))
    }

    if (cfg.security) {
      const sc = cfg.security
      if (sc.has_udun_prob !== undefined) security.value.hasUdunProb = sc.has_udun_prob
      if (sc.udun_brands) security.value.udunBrands = [...sc.udun_brands]
      if (sc.udun_status_weights) security.value.udunStatusWeights = { ...sc.udun_status_weights }
      if (sc.has_fingerprint_prob !== undefined) security.value.fingerprintProb = sc.has_fingerprint_prob
      if (sc.has_face_auth_prob !== undefined) security.value.faceAuthProb = sc.has_face_auth_prob
      if (sc.account_lock) {
        if (sc.account_lock.night_lock_prob !== undefined) security.value.nightLockProb = sc.account_lock.night_lock_prob
        if (sc.account_lock.overseas_lock_prob !== undefined) security.value.overseasLockProb = sc.account_lock.overseas_lock_prob
        if (sc.account_lock.online_pay_lock_prob !== undefined) security.value.onlinePayLockProb = sc.account_lock.online_pay_lock_prob
      }
    }

    if (cfg.service_probability) {
      const sv = cfg.service_probability
      if (sv.has_social_security !== undefined) service.value.has_social_security = sv.has_social_security
      if (sv.has_medical_insurance !== undefined) service.value.has_medical_insurance = sv.has_medical_insurance
      if (sv.has_housing_fund !== undefined) service.value.has_housing_fund = sv.has_housing_fund
      if (sv.has_personal_pension !== undefined) service.value.has_personal_pension = sv.has_personal_pension
    }

    if (cfg.benefits) {
      const bf = cfg.benefits
      if (bf.has_i_dou_prob !== undefined) benefits.value.hasIDouProb = bf.has_i_dou_prob
      if (bf.i_dou_range) { benefits.value.iDouMin = bf.i_dou_range[0]; benefits.value.iDouMax = bf.i_dou_range[1] }
      if (bf.i_dou_expiring_range) { benefits.value.iDouExpiringMin = bf.i_dou_expiring_range[0]; benefits.value.iDouExpiringMax = bf.i_dou_expiring_range[1] }
      if (bf.coupons_range) { benefits.value.couponsMin = bf.coupons_range[0]; benefits.value.couponsMax = bf.coupons_range[1] }
      if (bf.star_levels) benefits.value.starLevels = [...bf.star_levels]
      if (bf.star_points_range) { benefits.value.starPointsMin = bf.star_points_range[0]; benefits.value.starPointsMax = bf.star_points_range[1] }
      if (bf.green_energy_range) { benefits.value.greenEnergyMin = bf.green_energy_range[0]; benefits.value.greenEnergyMax = bf.green_energy_range[1] }
    }

    if (cfg.digital_rmb) {
      const dr = cfg.digital_rmb
      if (dr.wallet_type_weights) digitalRmb.value.walletTypeWeights = { ...dr.wallet_type_weights }
      if (dr.auto_recharge_prob !== undefined) digitalRmb.value.autoRechargeProb = dr.auto_recharge_prob
      if (dr.status_weights) digitalRmb.value.statusWeights = { ...dr.status_weights }
    }

    if (cfg.salary) {
      const sy = cfg.salary
      if (sy.has_salary_card_prob !== undefined) salary.value.hasSalaryCardProb = sy.has_salary_card_prob
      if (sy.excluded_occupations) salary.value.excludedOccupations = [...sy.excluded_occupations]
      if (sy.salary_ranges) salary.value.salaryRanges = { ...sy.salary_ranges }
      if (sy.has_company_prob !== undefined) salary.value.hasCompanyProb = sy.has_company_prob
      if (sy.payment_days) salary.value.paymentDays = [...sy.payment_days]
    }

    if (cfg.payment_agreements) {
      const pa = cfg.payment_agreements
      if (pa.has_prob !== undefined) paymentAgreements.value.hasProb = pa.has_prob
      if (pa.count_range) { paymentAgreements.value.countMin = pa.count_range[0]; paymentAgreements.value.countMax = pa.count_range[1] }
      if (pa.paused_prob !== undefined) paymentAgreements.value.pausedProb = pa.paused_prob
      if (pa.limit_options) paymentAgreements.value.limitOptions = [...pa.limit_options]
      if (pa.status_weights) paymentAgreements.value.statusWeights = { ...pa.status_weights }
      if (pa.utility_types) paymentAgreements.value.utilityTypes = pa.utility_types.map(u => ({ ...u }))
    }

    if (cfg.transactions) {
      const tx = cfg.transactions
      if (tx.count_range) { transactions.value.countMin = tx.count_range[0]; transactions.value.countMax = tx.count_range[1] }
      if (tx.types) transactions.value.types = [...tx.types]
      if (tx.amount_range) { transactions.value.amountMin = tx.amount_range[0]; transactions.value.amountMax = tx.amount_range[1] }
      if (tx.days_back) { transactions.value.daysMin = tx.days_back[0]; transactions.value.daysMax = tx.days_back[1] }
    }

    if (cfg.investment_profile?.preferences) {
      for (const level of riskLevels) {
        const p = cfg.investment_profile.preferences[level]
        if (p) {
          if (p.fund_types) investPrefs.value[level].fundTypes = [...p.fund_types]
          if (p.wealth_type) investPrefs.value[level].wealthTypes = [...p.wealth_type]
          if (p.holding_period) { investPrefs.value[level].holdingMin = p.holding_period[0]; investPrefs.value[level].holdingMax = p.holding_period[1] }
        }
      }
    }

    if (cfg.behavior) {
      const bh = cfg.behavior
      if (bh.app_version) {
        if (bh.app_version['>55']) behavior.value.appVersionOld = [...bh.app_version['>55']]
        if (bh.app_version.default) behavior.value.appVersionDefault = [...bh.app_version.default]
      }
      if (bh.login_frequency) behavior.value.loginFreq = [...bh.login_frequency]
      if (bh.channel_pool) behavior.value.channelPool = [...bh.channel_pool]
      if (bh.channel_count) { behavior.value.channelCountMin = bh.channel_count[0]; behavior.value.channelCountMax = bh.channel_count[1] }
      if (bh.frequent_menu_pool) behavior.value.frequentMenuPool = [...bh.frequent_menu_pool]
      if (bh.frequent_menu_count) { behavior.value.frequentMenuMin = bh.frequent_menu_count[0]; behavior.value.frequentMenuMax = bh.frequent_menu_count[1] }
    }

    if (cfg.insurance_products) insuranceProducts.value = cfg.insurance_products.map(p => ({ ...p }))
    if (cfg.bond_products) bondProducts.value = cfg.bond_products.map(p => ({ ...p }))
    if (cfg.precious_metals) preciousMetals.value = cfg.precious_metals.map(p => ({ ...p }))

    // Sync Str refs from loaded data
    phonePrefixesStr.value = arrStr(basic.value.phonePrefixes)
    billDaysStr.value = arrStr(creditCard.value.billDays)
    merchantPoolStr.value = arrStr(payees.value.merchantPool)
    repaymentNamesStr.value = arrStr(payees.value.repaymentNames)
    largeTermsStr.value = arrStr(deposits.value.largeTerms)
    fixedTermsStr.value = arrStr(deposits.value.fixedTerms)
    repaymentMethodsStr.value = arrStr(loans.value.repaymentMethods)
    udunBrandsStr.value = arrStr(security.value.udunBrands)
    starLevelsStr.value = arrStr(benefits.value.starLevels)
    paymentDaysStr.value = arrStr(salary.value.paymentDays)
    excludedOccupationsStr.value = arrStr(salary.value.excludedOccupations)
    limitOptionsStr.value = arrStr(paymentAgreements.value.limitOptions)
    transactionsTypesStr.value = arrStr(transactions.value.types)
    appVersionOldStr.value = arrStr(behavior.value.appVersionOld)
    appVersionDefaultStr.value = arrStr(behavior.value.appVersionDefault)
    loginFreqStr.value = arrStr(behavior.value.loginFreq)
    channelPoolStr.value = arrStr(behavior.value.channelPool)
    frequentMenuPoolStr.value = arrStr(behavior.value.frequentMenuPool)
    for (const level of riskLevels) {
      const ip = investPrefs.value[level]
      investFundTypesStr.value[level] = arrStr(ip.fundTypes)
      investWealthTypesStr.value[level] = arrStr(ip.wealthTypes)
    }
  } catch (e) {
    console.error('[ProfileControl] load error:', e)
    ElMessage.error('加载配置失败: ' + (e.message || e))
  }
})

// ========== 保存配置 ==========
async function saveAll() {
  saving.value = true
  try {
    const res = await api.config.get('bank_intent', 'profile_config')
    const cfg = res.data.content

    // Sync Str refs back to arrays
    basic.value.phonePrefixes = strArr(phonePrefixesStr.value)
    creditCard.value.billDays = strArr(billDaysStr.value)
    payees.value.merchantPool = strArr(merchantPoolStr.value)
    payees.value.repaymentNames = strArr(repaymentNamesStr.value)
    deposits.value.largeTerms = strArr(largeTermsStr.value)
    deposits.value.fixedTerms = strArr(fixedTermsStr.value)
    loans.value.repaymentMethods = strArr(repaymentMethodsStr.value)
    security.value.udunBrands = strArr(udunBrandsStr.value)
    benefits.value.starLevels = strArr(starLevelsStr.value)
    salary.value.paymentDays = strArr(paymentDaysStr.value)
    salary.value.excludedOccupations = strArr(excludedOccupationsStr.value)
    paymentAgreements.value.limitOptions = strArr(limitOptionsStr.value)
    transactions.value.types = strArr(transactionsTypesStr.value)
    behavior.value.appVersionOld = strArr(appVersionOldStr.value)
    behavior.value.appVersionDefault = strArr(appVersionDefaultStr.value)
    behavior.value.loginFreq = strArr(loginFreqStr.value)
    behavior.value.channelPool = strArr(channelPoolStr.value)
    behavior.value.frequentMenuPool = strArr(frequentMenuPoolStr.value)
    for (const level of riskLevels) {
      investPrefs.value[level].fundTypes = strArr(investFundTypesStr.value[level])
      investPrefs.value[level].wealthTypes = strArr(investWealthTypesStr.value[level])
    }

    cfg.basic_attributes = cfg.basic_attributes || {}
    cfg.basic_attributes.customer_tier_weights = { ...basic.value.customerTierWeights }
    cfg.basic_attributes.education_weights = { ...basic.value.educationWeights }
    cfg.basic_attributes.marital_weights = { ...basic.value.maritalWeights }
    cfg.basic_attributes.has_children_prob = basic.value.hasChildrenProb
    cfg.basic_attributes.is_same_city_prob = basic.value.isSameCityProb
    cfg.basic_attributes.age_range = [basic.value.ageMin, basic.value.ageMax]
    cfg.basic_attributes.risk_tolerance_range = [basic.value.riskMin, basic.value.riskMax]
    cfg.basic_attributes.phone_prefixes = [...basic.value.phonePrefixes]

    cfg.debit_card = cfg.debit_card || {}
    cfg.debit_card.level_weights = { ...debitCard.value.levelWeights }
    cfg.debit_card.account_type_weights = { ...debitCard.value.accountTypeWeights }
    cfg.debit_card.status_weights = { ...debitCard.value.statusWeights }
    cfg.debit_card.count = { single_prob: debitCard.value.singleProb, multi_max: debitCard.value.multiMax }
    cfg.debit_card.annual_fee_waived_prob = debitCard.value.annualFeeWaivedProb
    cfg.debit_card.age_factor_min = debitCard.value.ageFactorMin
    cfg.debit_card.age_factor_max = debitCard.value.ageFactorMax
    cfg.debit_card.available_balance_ratio = [debitCard.value.availBalanceRatioMin, debitCard.value.availBalanceRatioMax]
    cfg.debit_card.balance_distribution = {}
    for (const k of Object.keys(debitCard.value.balanceDistribution)) {
      try { cfg.debit_card.balance_distribution[k] = JSON.parse(balanceDistJson.value[k] || '{}') }
      catch { cfg.debit_card.balance_distribution[k] = debitCard.value.balanceDistribution[k] }
    }

    cfg.credit_card = cfg.credit_card || {}
    cfg.credit_card.has_probability = creditCard.value.hasProb
    cfg.credit_card.auto_repayment_prob = creditCard.value.autoRepayProb
    cfg.credit_card.has_points_prob = creditCard.value.hasPointsProb
    cfg.credit_card.status_weights = { ...creditCard.value.statusWeights }
    cfg.credit_card.used_limit_ratio = [creditCard.value.usedLimitRatioMin, creditCard.value.usedLimitRatioMax]
    cfg.credit_card.bill_days = [...creditCard.value.billDays]
    cfg.credit_card.high_limit_occupations = [...creditCard.value.highLimitOccupations]
    cfg.credit_card.high_limit_age = creditCard.value.highLimitAge
    cfg.credit_card.high_limit_multiplier = [creditCard.value.highLimitMultMin, creditCard.value.highLimitMultMax]
    cfg.credit_card.mid_limit_age = creditCard.value.midLimitAge
    cfg.credit_card.mid_limit_multiplier = [creditCard.value.midLimitMultMin, creditCard.value.midLimitMultMax]
    cfg.credit_card.points_range = [creditCard.value.pointsMin, creditCard.value.pointsMax]
    cfg.credit_card.age_credit_count = { ...creditCard.value.ageCreditCount }
    cfg.credit_card.credit_products = creditCard.value.products.map(p => ({ ...p }))

    cfg.payees = {
      has_prob: payees.value.hasProb,
      count_range: [payees.value.countMin, payees.value.countMax],
      is_frequent_prob: payees.value.isFrequentProb,
      has_phone_prob: payees.value.hasPhoneProb,
      merchant_pool: [...payees.value.merchantPool],
      repayment_names: [...payees.value.repaymentNames],
    }

    cfg.holdings_probability = { ...holdings.value }

    cfg.holdings_count = {
      fund_max_per_risk: holdingsCount.value.fundMaxPerRisk,
      wealth_max_per_risk: holdingsCount.value.wealthMaxPerRisk,
      insurance_count: [holdingsCount.value.insuranceMin, holdingsCount.value.insuranceMax],
      bond_count: [holdingsCount.value.bondMin, holdingsCount.value.bondMax],
      metals_count: [holdingsCount.value.metalsMin, holdingsCount.value.metalsMax],
      loan_max_by_age: holdingsCount.value.loanMaxByAge,
    }

    cfg.deposits = {
      has_large_deposit_prob: deposits.value.hasLargeProb,
      large_deposit_count: [deposits.value.largeCountMin, deposits.value.largeCountMax],
      large_deposit_terms: [...deposits.value.largeTerms],
      large_deposit_range: [deposits.value.largeAmountMin, deposits.value.largeAmountMax],
      large_deposit_rate_range: [deposits.value.largeRateMin, deposits.value.largeRateMax],
      has_fixed_deposit_prob: deposits.value.hasFixedProb,
      fixed_deposit_count: [deposits.value.fixedCountMin, deposits.value.fixedCountMax],
      fixed_deposit_terms: [...deposits.value.fixedTerms],
      fixed_deposit_range: [deposits.value.fixedAmountMin, deposits.value.fixedAmountMax],
      fixed_deposit_rate_range: [deposits.value.fixedRateMin, deposits.value.fixedRateMax],
      auto_rollover_prob: deposits.value.autoRolloverProb,
    }

    cfg.loans = {
      rate_ranges: { ...loanRates.value },
      repayment_methods: [...loans.value.repaymentMethods],
      overdue_prob: loans.value.overdueProb,
      is_mortgage_tax_deductible_prob: loans.value.isMortgageDeductibleProb,
      loan_types: loans.value.loanTypes.map(lt => ({ ...lt })),
    }

    cfg.security = {
      has_udun_prob: security.value.hasUdunProb,
      udun_brands: [...security.value.udunBrands],
      udun_status_weights: { ...security.value.udunStatusWeights },
      has_fingerprint_prob: security.value.fingerprintProb,
      has_face_auth_prob: security.value.faceAuthProb,
      account_lock: {
        night_lock_prob: security.value.nightLockProb,
        overseas_lock_prob: security.value.overseasLockProb,
        online_pay_lock_prob: security.value.onlinePayLockProb,
      },
    }

    cfg.service_probability = { ...service.value }

    cfg.benefits = {
      has_i_dou_prob: benefits.value.hasIDouProb,
      i_dou_range: [benefits.value.iDouMin, benefits.value.iDouMax],
      i_dou_expiring_range: [benefits.value.iDouExpiringMin, benefits.value.iDouExpiringMax],
      coupons_range: [benefits.value.couponsMin, benefits.value.couponsMax],
      star_levels: [...benefits.value.starLevels],
      star_points_range: [benefits.value.starPointsMin, benefits.value.starPointsMax],
      green_energy_range: [benefits.value.greenEnergyMin, benefits.value.greenEnergyMax],
    }

    cfg.digital_rmb = {
      wallet_type_weights: { ...digitalRmb.value.walletTypeWeights },
      auto_recharge_prob: digitalRmb.value.autoRechargeProb,
      status_weights: { ...digitalRmb.value.statusWeights },
    }

    cfg.salary = {
      has_salary_card_prob: salary.value.hasSalaryCardProb,
      excluded_occupations: [...salary.value.excludedOccupations],
      salary_ranges: { ...salary.value.salaryRanges },
      has_company_prob: salary.value.hasCompanyProb,
      payment_days: [...salary.value.paymentDays],
    }

    cfg.payment_agreements = {
      has_prob: paymentAgreements.value.hasProb,
      count_range: [paymentAgreements.value.countMin, paymentAgreements.value.countMax],
      paused_prob: paymentAgreements.value.pausedProb,
      limit_options: [...paymentAgreements.value.limitOptions],
      status_weights: { ...paymentAgreements.value.statusWeights },
      utility_types: paymentAgreements.value.utilityTypes.map(u => ({ ...u })),
    }

    cfg.transactions = {
      count_range: [transactions.value.countMin, transactions.value.countMax],
      types: [...transactions.value.types],
      amount_range: [transactions.value.amountMin, transactions.value.amountMax],
      days_back: [transactions.value.daysMin, transactions.value.daysMax],
    }

    const investProfile = {}
    for (const level of riskLevels) {
      const ip = investPrefs.value[level]
      investProfile[level] = {
        fund_types: [...ip.fundTypes],
        wealth_type: [...ip.wealthTypes],
        holding_period: [ip.holdingMin, ip.holdingMax],
      }
    }
    cfg.investment_profile = { preferences: investProfile }

    cfg.behavior = {
      app_version: {
        '>55': [...behavior.value.appVersionOld],
        default: [...behavior.value.appVersionDefault],
      },
      login_frequency: [...behavior.value.loginFreq],
      channel_pool: [...behavior.value.channelPool],
      channel_count: [behavior.value.channelCountMin, behavior.value.channelCountMax],
      frequent_menu_pool: [...behavior.value.frequentMenuPool],
      frequent_menu_count: [behavior.value.frequentMenuMin, behavior.value.frequentMenuMax],
    }

    cfg.insurance_products = insuranceProducts.value.map(p => ({ ...p }))
    cfg.bond_products = bondProducts.value.map(p => ({ ...p }))
    cfg.precious_metals = preciousMetals.value.map(p => ({ ...p }))

    await api.config.update('bank_intent', 'profile_config', cfg)
    ElMessage.success('所有配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    saving.value = false
  }
}

async function restoreDefault() {
  try {
    await ElMessageBox.confirm(
      '将清除当前用户保存的全部画像参数，并恢复内置默认值。已上传的产品 CSV 不会删除。此操作不能撤销。是否继续？',
      '恢复默认用户画像',
      { confirmButtonText: '恢复默认', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  restoring.value = true
  try {
    await api.config.restoreDefault('bank_intent', 'profile_config')
    ElMessage.success('用户画像已恢复默认')
    window.location.reload()
  } catch (e) {
    ElMessage.error('恢复失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    restoring.value = false
  }
}
</script>
