export const ROLES={admin:'调拨主管',chemist:'化验员',viewer:'船代观察员'};
export const SAMPLE_STATES={received:'待比对',queued:'比对中',qualified:'原样合格',anomaly:'异常待复检',retested:'复检合格',rejected:'复检未过',failed:'计算失败'};
export const AUDIT_ACTIONS={tank_registered:'储罐登记',tank_state:'储罐状态调整',sample_received:'油样收件',sample_compared:'密度分布比对',sample_retested:'化验复检',transfer_requested:'调拨申请',transfer_released:'主管调拨放行',permit_planned:'清线计划',line_registered:'管线登记',line_permitted:'清线许可',window_planned:'受油窗口计划',window_confirmed:'泊位窗口确认',berth_registered:'泊位登记',harbor_occupied:'放行占用资源',harbor_completed:'输油完工释放',retained_sealed:'燃油留样封存',retest_commissioned:'封样复检委托',retest_reported:'委托检验报告',retest_closed:'委托复检结案',tray_registered:'贴签复核盘登记',tray_bottle_added:'复盘瓶样登记',tray_bottle_removed:'复盘瓶样移出',tray_candidates_updated:'候选罐调整',tray_analysis_queued:'整盘分析受理',tray_adopted:'主管采纳整盘归属'};

export const RECEIPT_STATES={planned:'计划到港',inspected:'化验核对通过',received:'已入罐冻结'};
export const RECONCILIATION_STATES={matched:'容差内待签',variance:'超差待调查',closed:'主管已结案'};
export const TRAY_STATES={draft:'登记中',queued:'核算中',suggested:'建议待采纳',review:'并列待人工核签',adopted:'已采纳冻结',failed:'核算失败可恢复'};
