# ValuationSystem — 估值跑批工作台（独立项目）

指数估值跑批工作台：用估值技能逐家跑指数成分券，估值替代价格、按权重合成指数点位。
先落地上证50（50 条成分券），上证180、科创50 随后扩展。

## 形态

另起炉灶的独立项目，但形式建立在 dsh 网页版（dsh-web-app）上：

- **独立仓库（本仓库）**：与 FactorLab 的 csi-dsh 完全隔离，不含任何 csi-dsh 源码；dsh 底座（dsh-base / dsh-web-app）仅作运行时依赖，从 `~/workspace/csi-dsh` 检出提供
- 包 `@valuation/workbench` 以 link 方式挂进独立 profile `~/.dsh/profiles/valuation/`
- 独立实例：`bash ~/workspace/valuation-up.sh` 起在 3081（FactorLab 在 3080，互不干扰）
- 独立数据目录：`DSH_HOME=~/.dsh-valuation`（会话/工作区/附件与 FactorLab 的 `~/.dsh` 互不可见）
- 品牌名 ValuationSystem（禁用上游 ui-brand-official 插件，由本包注入侧栏品牌 + 改写页面标题）
- 客户端插件 claim 上游 `ui-workbench` 面板（profile 里已停用上游行），渲染六步流程页面

## 六步流程

1. 参数确认（写死参数拉成表单：舆情轮数、方法加权比例、增速、永续增长率、WACC、β）
2. 选择指数（上证50 本期落地，上证180/科创50 后续扩展）
3. 成分券权重（因子×市值→归一化权重，由指数成分券表自动生成）
4. 估值日期（一次一天；周频由定时任务自动带入）
5. 并行度（每批 3 / 10 条，先试跑再定）
6. 运行报告（逐券报告 ×50 + 总结报告：拟合点位 + 两版对比）

点位合成：权重因子×当日市值→归一化当日权重；个股估值×权重→加权求和。不能等权平均。

## 目录

- `packages/workbench/` — @valuation/workbench bundle（client 插件 + 页面 + 后续 preset/技能）
- `profiles/valuation/` — 独立 profile 配置（package.json / cordis.yml / cordis.patch.yml），部署到 `~/.dsh/profiles/valuation/`（node_modules 不入库）
- `scripts/valuation-up.sh` / `scripts/valuation-down.sh` — 起停脚本，部署到 `~/workspace/`
- 静态原型参照稿：`valuation-batch-workbench.html`（工作目录，不在本仓库）

## 构建与部署

```bash
cd ~/workspace/valuation-workbench && pnpm install
cd packages/workbench && pnpm run build   # node build.mjs → lib/client.js + lib/index.js
cd ~/.dsh/profiles/valuation && pnpm install   # 建立 @valuation/workbench 符号链接
bash ~/workspace/valuation-down.sh && bash ~/workspace/valuation-up.sh
```

改客户端代码后无需重启实例：重新 build 后浏览器刷新即生效（profile patchReload live）。
改 profile 配置：把 `profiles/valuation/` 里的文件同步到 `~/.dsh/profiles/valuation/` 后按需 `pnpm install`。
