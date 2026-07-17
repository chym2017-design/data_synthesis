"""
流水线编排模块

定义完整的数据合成流水线：gen -> llm -> filter -> export。
"""

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from cn2an import an2cn

from synth_engine import templates  # noqa: F401
from synth_engine.core.config import ConfigLoader, SynthConfigModel, ProfileConfigModel, deep_merge
from synth_engine.core.models import SynthSample, RunStatus
from synth_engine.core.profile_gen import ConfigDrivenProfileGenerator
from synth_engine.core.utils import weighted_choice
from synth_engine.llm.parallel import run_llm_para
from synth_engine.limits import LIMITS
from synth_engine.templates.base import SynthTemplate
from synth_engine.templates.registry import TemplateRegistry


class SynthesisPipeline:
    """数据合成流水线"""

    def __init__(
        self,
        template_name: str,
        template_dir: str,
        run_dir: str,
        synth_config: Optional[SynthConfigModel] = None,
        status_callback: Optional[Callable[[RunStatus], None]] = None,
    ):
        self.template_name = template_name
        self.template: SynthTemplate = TemplateRegistry.get(template_name)
        self.template_dir = Path(template_dir)
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.synth_config = synth_config
        self.status_callback = status_callback

        # 加载配置
        self.intent_config = self.template.load_intent_config(
            str(self.template_dir / "intent.json")
        )
        if synth_config is None:
            synth_cfg_path = self.template_dir / "synth_config.yaml"
            if synth_cfg_path.exists():
                self.synth_config = SynthConfigModel(**self.template.load_synth_config(str(synth_cfg_path)))
            else:
                self.synth_config = SynthConfigModel()

        # 加载画像配置
        profile_cfg_path = self.template_dir / "profile_config.yaml"
        if profile_cfg_path.exists():
            loader = ConfigLoader()
            raw_cfg = loader.load_yaml(str(profile_cfg_path))
            raw_cfg["__config_dir__"] = str(self.template_dir)
            user_path = self.template_dir / "profile_config.user.yaml"
            if user_path.exists():
                user_cfg = loader.load_yaml(str(user_path))
                raw_cfg = deep_merge(raw_cfg, user_cfg)
            self._raw_profile_cfg = raw_cfg
            self.profile_config = ProfileConfigModel(**raw_cfg)
        else:
            self.profile_config = ProfileConfigModel()
            self._raw_profile_cfg = {}

        self._emit_status(RunStatus(run_id=self.run_dir.name, stage="initialized", message="流水线初始化完成"))

    def _emit_status(self, status: RunStatus):
        if self.status_callback:
            self.status_callback(status)

    def generate_intent_samples(self, num_samples: int) -> Tuple[List[SynthSample], List[SynthSample]]:
        """
        Step 1: 生成意图样本，并拆分为单轮/多轮两组
        返回 (single_round_samples, multi_round_samples)
        """
        self._emit_status(RunStatus(run_id=self.run_dir.name, stage="generating", total=num_samples, current=0, message="生成意图样本..."))

        intent = self.intent_config.get("intent", {})
        intent_names = list(intent)
        intent_weights = [intent[k].get("weight", 1.0) for k in intent]
        intent_probs = np.array(intent_weights) / sum(intent_weights)

        cfg = self.synth_config
        profile_gen = ConfigDrivenProfileGenerator(self._raw_profile_cfg or self.profile_config)
        single_round_ratio = getattr(cfg, "single_round_ratio", 0.05)

        all_samples = []
        for idx in range(num_samples):
            # 选择意图对
            (intent_i, sub_i), (intent_j, sub_j) = self._select_intent_pair(
                intent, intent_names, intent_probs
            )
            intent_i_str = f"{intent_i}，{sub_i['name']}"
            intent_j_str = f"{intent_j}，{sub_j['name']}"

            # 生成用户画像
            profile = profile_gen.generate_user_profile(user_id=f"USER_{100000 + idx}")
            user_profile_md = self._format_profile_simple(profile)

            # 计算轮数
            if intent_i_str == intent_j_str:
                probs = np.array(cfg.round_distribution.single_intent)
            else:
                probs = np.array(cfg.round_distribution.multi_intent)
            round_num = int(np.random.choice(probs[:, 0].astype(int), p=probs[:, 1]))
            num_sen = 2 * round_num

            # 生成语气
            yuqi = weighted_choice(
                list(cfg.tone_distribution.keys()),
                list(cfg.tone_distribution.values()),
            )

            # 生成心情（按概率）
            xinqing = ""
            if np.random.rand() < cfg.mood.probability:
                xinqing = np.random.choice(cfg.mood.emotions)
                yuqi = f"{yuqi}，用户当前的心理状态为{xinqing}"

            # 获取子意图描述
            sub_desc_1 = sub_i.get("description", sub_i["name"])
            sub_desc_2 = sub_j.get("description", sub_j["name"])

            # 意图切换约束
            intent_constraint = ""
            if sub_i["name"] != sub_j["name"] and np.random.rand() < cfg.intent_transition_constraint.switch_at_terminal_turn_ratio:
                intent_constraint = """## 时序意图约束（Sequential Intent Constraint）

当起始子意图与目标子意图不一致时，对话应遵循**延迟集中式意图切换**原则：

- **前置一致**：除最后一轮外，所有对话轮次须严格限定在起始子意图的业务语义范围内；
- **终止轮切换**：意图切换仅在最后一轮发生，用户在此轮明确表达目标子意图；
- **边界清晰**：不存在中间过渡状态，切换点唯一且明确。"""

            sample = SynthSample(
                sample_id=idx,
                intent_1=intent_i,
                intent_2=intent_j,
                sub_intent_1=sub_i["name"],
                sub_intent_2=sub_j["name"],
                sub_intent_desc_1=sub_desc_1,
                sub_intent_desc_2=sub_desc_2,
                target={"意图": intent_j, "子意图": sub_j["name"]},
                user_profile=user_profile_md,
                round_num=round_num,
                num_sen=num_sen,
                yuqi=yuqi,
                xinqing=xinqing,
                menu_list="",
                intent_transition_constraint=intent_constraint,
                single_round=False,
            )
            all_samples.append(sample)

            if (idx + 1) % 100 == 0:
                self._emit_status(RunStatus(
                    run_id=self.run_dir.name, stage="generating",
                    total=num_samples, current=idx + 1,
                    message=f"已生成 {idx + 1}/{num_samples} 条样本",
                ))

        # 标记单轮样本
        single_count = max(1, int(round(num_samples * single_round_ratio)))
        indices = np.random.choice(num_samples, size=single_count, replace=False)
        for i in indices:
            all_samples[i].single_round = True

        # 确保至少有一条单轮
        if not any(s.single_round for s in all_samples):
            all_samples[0].single_round = True

        # 打乱顺序
        np.random.shuffle(all_samples)

        # 拆分单轮/多轮
        single_round = [s for s in all_samples if s.single_round]
        multi_round = [s for s in all_samples if not s.single_round]

        self._emit_status(RunStatus(
            run_id=self.run_dir.name, stage="generating",
            total=num_samples, current=num_samples,
            message=f"意图样本生成完成: 单轮 {len(single_round)} 条，多轮 {len(multi_round)} 条",
        ))
        return single_round, multi_round

    def _select_intent_pair(self, intent: Dict, intent_names: List, intent_probs: np.ndarray):
        """选择起始意图和目标意图对"""
        cfg = self.synth_config.intent_transition

        intent_start, sub_start = self._select_single_intent(intent, intent_names, intent_probs)
        rand = np.random.rand()

        if rand < cfg.single_intent_prob:
            # 单意图：无跳转，起始=结束
            intent_end = intent_start
            sub_end = sub_start
        elif rand < cfg.single_intent_prob + cfg.multi_intent_prob * cfg.same_intent_multi_subintent_ratio:
            # 多意图 → 同意图内换子意图
            intent_end = intent_start
            sub_end = np.random.choice(intent[intent_start]["sub_intent"])
        else:
            # 多意图 → 跨意图跳转
            intent_end, sub_end = self._select_single_intent(intent, intent_names, intent_probs)

        return (intent_start, sub_start), (intent_end, sub_end)

    def _select_single_intent(self, intent: Dict, intent_names: List, intent_probs: np.ndarray):
        """选择单个意图和子意图"""
        name = np.random.choice(intent_names, p=intent_probs)
        sub = np.random.choice(intent[name]["sub_intent"])
        return name, sub

    def _format_profile_simple(self, profile: Dict) -> str:
        """简化版用户画像格式化"""
        basic = profile.get("basic_info", {})
        assets = profile.get("asset_summary", {})
        lines = [
            "### 用户基本信息",
            f"- 姓名：{basic.get('name', '未知')}",
            f"- 性别：{basic.get('gender', '未知')}",
            f"- 年龄：{basic.get('age', 0)}岁",
            f"- 职业：{basic.get('occupation', '未知')}",
            f"- 城市：{basic.get('city', '未知')}",
            f"- 客户层级：{basic.get('customer_tier', '普通')}",
            "",
            "### 资产总览",
            f"- 总资产：{assets.get('total_assets', 0):,.2f}元",
            f"- 总负债：{assets.get('total_liability', 0):,.2f}元",
            f"- 净资产：{assets.get('net_assets', 0):,.2f}元",
        ]
        return "\n".join(lines)

    def call_llm(
        self,
        samples: List[SynthSample],
        llm_configs: List[Dict],
        para: int = LIMITS.model_parallelism.default,
        template_name: str = "multi_round.md",
        progress_offset: int = 0,
        progress_total: Optional[int] = None,
    ):
        """
        Step 2: 调用 LLM 生成对话
        """
        overall_total = progress_total if progress_total is not None else len(samples)
        phase_label = "多轮对话" if template_name == "multi_round.md" else "单轮对话"
        self._emit_status(RunStatus(
            run_id=self.run_dir.name, stage="calling_llm",
            total=overall_total, current=progress_offset,
            message=f"正在生成{phase_label}... (0/{len(samples)})",
        ))

        prompt_path = str(self.template_dir / "prompts" / template_name)
        prompts = [self.template.build_prompt(s, prompt_path) for s in samples]

        def progress_callback(done: int, phase_total: int):
            self._emit_status(RunStatus(
                run_id=self.run_dir.name,
                stage="calling_llm",
                total=overall_total,
                current=progress_offset + done,
                message=(
                    f"正在生成{phase_label}... ({done}/{phase_total})，"
                    f"模型总进度 {progress_offset + done}/{overall_total}"
                ),
            ))

        df_results = run_llm_para(
            prompts,
            para,
            llm_configs,
            progress_callback=progress_callback,
        )

        if df_results is None:
            self._emit_status(RunStatus(
                run_id=self.run_dir.name, stage="error",
                message="LLM 调用失败", error="LLM call returned None",
            ))
            return samples

        for i, (_, row) in enumerate(df_results.iterrows()):
            if i < len(samples):
                samples[i].response = row.get("response", "")
                samples[i].model = row.get("model", "")
                samples[i].status_code = row.get("status_code", 0)
                samples[i].duration = row.get("duration", 0.0)

        log_cols = ["idx", "question", "model", "status_code", "err_msg", "duration"]
        cols = [c for c in log_cols if c in df_results.columns]
        # 多轮和单轮分两批调用，日志必须追加，不能让后一批覆盖前一批。
        with open(self.run_dir / "llm_log.jsonl", "a", encoding="utf-8") as log_file:
            df_results[cols].to_json(
                log_file,
                orient="records", lines=True, force_ascii=False,
            )

        self._emit_status(RunStatus(
            run_id=self.run_dir.name, stage="calling_llm",
            total=overall_total, current=progress_offset + len(samples),
            message=f"{phase_label}生成完成: {len(samples)} 条，模型总进度 {progress_offset + len(samples)}/{overall_total}",
        ))
        return samples

    def split_single_round(self, samples: List[SynthSample]) -> List[SynthSample]:
        """
        Step 2.5: 拆分单轮样本
        单轮 prompt 一次生成多条"用户："请求，需要拆分成独立样本
        """
        result = []
        for s in samples:
            text = str(s.response)
            # 移除 markdown 代码块标记
            text = re.sub(r"```[a-zA-Z]*\n?", "", text)
            text = re.sub(r"```\n?", "", text)

            # 提取所有"用户："开头的行
            user_lines = [line.strip() for line in text.split("\n") if line.strip().startswith("用户：")]
            if user_lines:
                for j, line in enumerate(user_lines):
                    new_sample = SynthSample(
                        sample_id=s.sample_id * 1000 + j,
                        intent_1=s.intent_1,
                        intent_2=s.intent_2,
                        sub_intent_1=s.sub_intent_1,
                        sub_intent_2=s.sub_intent_2,
                        sub_intent_desc_1=s.sub_intent_desc_1,
                        sub_intent_desc_2=s.sub_intent_desc_2,
                        target=s.target,
                        user_profile=s.user_profile,
                        round_num=1,
                        num_sen=1,
                        yuqi=s.yuqi,
                        xinqing=s.xinqing,
                        menu_list=s.menu_list,
                        intent_transition_constraint=s.intent_transition_constraint,
                        single_round=True,
                        response=line,
                        query=line,
                        model=s.model,
                        duration=s.duration,
                        status_code=s.status_code,
                    )
                    result.append(new_sample)
            else:
                # 没提取到用户行，保留原始样本
                s.query = text.strip()
                result.append(s)
        return result

    def filter_and_merge(self, samples: List[SynthSample]) -> List[SynthSample]:
        """
        Step 3: 格式过滤
        """
        self._emit_status(RunStatus(
            run_id=self.run_dir.name, stage="filtering",
            total=len(samples), current=0, message="格式过滤...",
        ))

        valid = [s for s in samples if self.template.validate_response(s.response)]
        for s in valid:
            if not s.query:
                s.query = self.template.extract_query(s.response)

        self._emit_status(RunStatus(
            run_id=self.run_dir.name, stage="filtering",
            total=len(samples), current=len(valid),
            message=f"过滤后有效数据: {len(valid)}/{len(samples)}",
        ))
        return valid

    def export_data(self, samples: List[SynthSample]) -> str:
        """
        Step 4: 导出数据（CSV + JSONL）
        """
        self._emit_status(RunStatus(
            run_id=self.run_dir.name, stage="exporting",
            message="导出数据...",
        ))

        # 导出 data.csv
        records = [s.to_dict() for s in samples]
        df = pd.DataFrame(records)
        csv_path = str(self.run_dir / "data.csv")
        df.to_csv(csv_path, index=False)

        # 导出 sft.jsonl
        jsonl_path = str(self.run_dir / "sft.jsonl")
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for s in samples:
                controller_data = self.template.gen_controller_data(s)
                f.write(json.dumps(controller_data, ensure_ascii=False) + "\n")

        self._emit_status(RunStatus(
            run_id=self.run_dir.name, stage="done",
            total=len(samples), current=len(samples),
            message=f"数据导出完成: CSV={csv_path}, JSONL={jsonl_path}",
        ))
        return csv_path

    def run(
        self,
        num_samples: int,
        llm_configs: List[Dict],
        para: int = LIMITS.model_parallelism.default,
    ) -> str:
        """执行完整流水线"""
        single_round, multi_round = self.generate_intent_samples(num_samples)

        # 分别调用 LLM，但对前端呈现为一个连续、单调递增的模型总进度。
        llm_total = len(multi_round) + len(single_round)
        llm_completed = 0
        if multi_round:
            multi_round = self.call_llm(
                multi_round, llm_configs, para, "multi_round.md",
                progress_offset=llm_completed, progress_total=llm_total,
            )
            llm_completed += len(multi_round)
        if single_round:
            single_round = self.call_llm(
                single_round, llm_configs, para, "single_round.md",
                progress_offset=llm_completed, progress_total=llm_total,
            )

        # 拆分单轮样本
        single_round = self.split_single_round(single_round)

        # 合并 + 过滤
        all_samples = multi_round + single_round
        valid_samples = self.filter_and_merge(all_samples)

        output_path = self.export_data(valid_samples)
        return output_path
