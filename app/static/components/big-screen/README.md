# 数智大屏组件库（第一阶段提取）

基于开源项目 [Big-Screen-Vue-Datav-Echarts](https://gitcode.com/gh_mirrors/bi/Big-Screen-Vue-Datav-Echarts) 完成第一阶段资源剥离与核心组件提取。

## 目录结构

```
big-screen/
├── data-view/              # DataV 大屏装饰组件使用示例
│   ├── index.vue           # 首页大屏整体布局（含 dv-decoration、dv-border-box 使用）
│   ├── bottomRight.vue     # 右下区域 DataV 装饰示例
│   ├── centerLeft1.vue     # 左中区域 DataV 装饰示例
│   └── centerLeft2.vue     # 左中第二区域 DataV 装饰示例
├── echarts/
│   ├── charts/             # ECharts 通用图表封装
│   │   ├── bottomLeftChart.vue
│   │   ├── bottomRightChart.vue
│   │   ├── bottomRightChartMap.vue
│   │   ├── centerChartRate.vue
│   │   ├── centreLeft1Chart.vue
│   │   ├── centreLeft2Chart.vue
│   │   ├── centreRight2Chart1.vue
│   │   ├── Earth3DChart.vue      # ECharts-GL 三维地球组件占位
│   │   └── WordCloudChart.vue    # echarts-wordcloud 词云组件占位
│   └── utils/              # ECharts 工具
│       ├── index.js        # 通用工具函数（含 debounce）
│       └── resizeMixins.js # Vue 图表自适应 resize 混入
└── layout/                 # 自适应布局样式
    ├── flexible.js         # rem 自适应方案
    ├── _variables.scss     # SCSS 变量
    ├── index.scss          # 大屏主样式
    ├── style.scss          # 通用样式
    └── pageBg.png          # 大屏背景图
```

## 已提取核心资源

1. **DataV 大屏装饰组件**：`dv-decoration-*`、`dv-border-box-*` 使用示例
2. **ECharts 通用图表封装**：折线图、柱状图、饼图、地图等图表组件
3. **ECharts-GL 三维地球组件**：`Earth3DChart.vue`（需安装 `echarts-gl`）
4. **echarts-wordcloud 词云组件**：`WordCloudChart.vue`（需安装 `echarts-wordcloud`）
5. **自适应布局样式**：`flexible.js` + SCSS 大屏样式

## 使用依赖

```bash
npm install @jiaminghi/data-view echarts echarts-gl echarts-wordcloud
```

## 路径适配说明

第一阶段已统一内部相对路径，组件内引用均按当前目录结构调整：
- `echarts/charts/*.vue` 引用 `../utils/resizeMixins`
- `echarts/utils/resizeMixins.js` 引用 `./index`
- `data-view/*.vue` 引用 `../echarts/charts/*`
- `data-view/index.vue` 引用 `../layout/index.scss`
- `layout/index.scss` 引用 `./pageBg.png`
- 地图组件 `bottomRightChartMap.vue` 中的 echarts 地图数据引用已注释，第二阶段按构建环境引入

## 注意事项

- 当前 yingyue-final 为 Tornado 后端渲染项目，无 Vue 构建环境，`.vue` 文件需在第二阶段接入 Vue 构建环境后使用。
- `Earth3DChart.vue` 和 `WordCloudChart.vue` 为占位组件，需安装 `echarts-gl`、`echarts-wordcloud` 并接入真实数据后完善。
- `data-view/index.vue` 为原模板首页布局参考，其中 `centerRight1`、`centerRight2`、`center`、`bottomLeft` 等子组件未提取，第二阶段需根据瞭望系统需求重新设计布局。
