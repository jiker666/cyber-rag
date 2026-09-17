package com.cyberrag.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cyberrag.entity.Conversation;
import org.apache.ibatis.annotations.Mapper;

/**
 * conversation 表 Mapper。
 */
@Mapper
public interface ConversationMapper extends BaseMapper<Conversation> {
}
