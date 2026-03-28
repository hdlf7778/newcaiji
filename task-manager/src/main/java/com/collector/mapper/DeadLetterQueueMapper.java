package com.collector.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.collector.entity.DeadLetterQueue;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface DeadLetterQueueMapper extends BaseMapper<DeadLetterQueue> {
}
