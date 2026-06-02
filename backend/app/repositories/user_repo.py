from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AdminLog,
    Notification,
    Referral,
    TokenActionType,
    TokenTransaction,
    User,
)
from app.utils.formatters import generate_referral_code


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.username == username.lstrip("@"))
        )
        return result.scalar_one_or_none()

    async def get_by_referral_code(self, code: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.referral_code == code)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        referred_by_id: Optional[int] = None,
        is_admin: bool = False,
    ) -> User:
        user = User(
            id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            referral_code=generate_referral_code(user_id),
            referred_by_id=referred_by_id,
            is_admin=is_admin,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_or_create(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        referred_by_id: Optional[int] = None,
        is_admin: bool = False,
    ) -> tuple[User, bool]:
        user = await self.get_by_id(user_id)
        if user:
            user.username = username or user.username
            user.first_name = first_name or user.first_name
            user.last_name = last_name or user.last_name
            user.last_active = datetime.now(timezone.utc)
            await self.session.flush()
            return user, False
        user = await self.create(
            user_id, username, first_name, last_name, referred_by_id, is_admin
        )
        return user, True

    async def count_all(self) -> int:
        result = await self.session.execute(select(func.count(User.id)))
        return result.scalar() or 0

    async def count_active(self, days: int = 7) -> int:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.session.execute(
            select(func.count(User.id)).where(User.last_active >= since)
        )
        return result.scalar() or 0

    async def get_leaderboard(self, limit: int = 10) -> list[User]:
        result = await self.session.execute(
            select(User)
            .where(User.is_banned == False)
            .order_by(User.total_earned.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_rank(self, user_id: int) -> int:
        user = await self.get_by_id(user_id)
        if not user:
            return 0
        result = await self.session.execute(
            select(func.count(User.id)).where(
                User.total_earned > user.total_earned,
                User.is_banned == False,
            )
        )
        return (result.scalar() or 0) + 1

    async def search(self, query: str, limit: int = 10) -> list[User]:
        conditions = []
        if query.isdigit():
            conditions.append(User.id == int(query))
        conditions.append(User.username.ilike(f"%{query.lstrip('@')}%"))
        result = await self.session.execute(
            select(User).where(or_(*conditions)).limit(limit)
        )
        return list(result.scalars().all())

    async def get_all_ids(self, sponsors_only: bool = False) -> list[int]:
        stmt = select(User.id).where(User.is_banned == False)
        if sponsors_only:
            stmt = stmt.where(User.is_sponsor == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def ban(self, user_id: int, banned: bool = True) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(is_banned=banned)
        )

    async def log_admin_action(
        self,
        admin_id: int,
        action: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        details: Optional[str] = None,
    ) -> None:
        self.session.add(
            AdminLog(
                admin_id=admin_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details,
            )
        )

    async def create_notification(
        self, user_id: int, title: str, message: str
    ) -> None:
        self.session.add(
            Notification(user_id=user_id, title=title, message=message)
        )

    async def add_tokens(
        self,
        user_id: int,
        amount: int,
        action_type: TokenActionType,
        reason: Optional[str] = None,
        admin_id: Optional[int] = None,
        reference_id: Optional[str] = None,
    ) -> User:
        user = await self.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        user.token_balance += amount
        if amount > 0:
            user.total_earned += amount
        self.session.add(
            TokenTransaction(
                user_id=user_id,
                amount=amount,
                balance_after=user.token_balance,
                action_type=action_type,
                reason=reason,
                admin_id=admin_id,
                reference_id=reference_id,
            )
        )
        await self.session.flush()
        return user

    async def remove_tokens(
        self,
        user_id: int,
        amount: int,
        action_type: TokenActionType,
        reason: Optional[str] = None,
        admin_id: Optional[int] = None,
    ) -> User:
        user = await self.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        if user.token_balance < amount:
            raise ValueError("Insufficient balance")
        user.token_balance -= amount
        user.total_spent += amount
        self.session.add(
            TokenTransaction(
                user_id=user_id,
                amount=-amount,
                balance_after=user.token_balance,
                action_type=action_type,
                reason=reason,
                admin_id=admin_id,
            )
        )
        await self.session.flush()
        return user

    async def set_tokens(
        self,
        user_id: int,
        balance: int,
        admin_id: int,
        reason: Optional[str] = None,
    ) -> User:
        user = await self.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        diff = balance - user.token_balance
        user.token_balance = balance
        self.session.add(
            TokenTransaction(
                user_id=user_id,
                amount=diff,
                balance_after=balance,
                action_type=TokenActionType.ADMIN_SET,
                reason=reason,
                admin_id=admin_id,
            )
        )
        await self.session.flush()
        return user

    async def create_referral(
        self, referrer_id: int, referred_id: int, reward_amount: int
    ) -> Referral:
        referral = Referral(
            referrer_id=referrer_id,
            referred_id=referred_id,
            reward_amount=reward_amount,
        )
        self.session.add(referral)
        await self.session.flush()
        return referral

    async def get_referral_by_referred(self, referred_id: int) -> Optional[Referral]:
        result = await self.session.execute(
            select(Referral).where(Referral.referred_id == referred_id)
        )
        return result.scalar_one_or_none()
