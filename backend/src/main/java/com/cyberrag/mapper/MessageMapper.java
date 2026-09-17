package com.cyberrag.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cyberrag.entity.Message;
import org.apache.ibatis.annotations.Mapper;

/**
 * message 表 Mapper。
 */
@Mapper
public interface MessageMapper extends BaseMapper<Message> {
}
